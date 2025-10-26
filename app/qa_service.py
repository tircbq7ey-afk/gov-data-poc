import os
import time
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# === 環境変数/メタ ===
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# === Health ===
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round(time.time() - START_TS, 2),
    }

# === Root ===
@app.get("/")
def root():
    return {"ok": True, "service": "gov-data-poc", "version": VERSION}

# === 型定義 ===
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

# === /ask (GET) ===
@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(..., title="Q"),
    lang: str = Query("ja", title="Lang"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # ここはPoCのダミー応答。必要なら検索/推論を差し込む
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# === /feedback (POST) ===
@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)

    # ./data/feedback/YYYYMMDD.jsonl に追記
    base = "./data/feedback"
    os.makedirs(base, exist_ok=True)
    out = os.path.join(base, f"{datetime.utcnow():%Y%m%d}.jsonl")

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": out})

# === /admin/reindex (POST) ===
@app.post("/admin/reindex")
def admin_reindex(
    payload: Dict[str, Any] = Body(default_factory=dict),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    """
    再インデックスのトリガ。実処理を後段に置く場合でも、
    flags ディレクトリにフラグファイルを置く形にしておくと運用が楽。
    """
    _require(x_api_key)

    flags_dir = "./data/flags"
    os.makedirs(flags_dir, exist_ok=True)

    # --force で毎回ユニークフラグを作る（既存ジョブがあるなら上書き/スキップ等は運用で調整）
    force = bool(payload.get("force", False))
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    flag_name = "reindex.force" if force else "reindex"
    flag_path = os.path.join(flags_dir, f"{flag_name}.{stamp}")

    with open(flag_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"force": force, "ts": stamp}))

    return JSONResponse({"ok": True, "path": flag_path})
