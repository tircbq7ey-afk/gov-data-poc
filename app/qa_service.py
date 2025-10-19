import os
import time
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ====== 基本情報 / 認証 ======
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

def _require(x_api_key: Optional[str]) -> None:
    """x-api-key 認証。設定されていれば一致を要求。"""
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ====== FastAPI ======
app = FastAPI(title="gov-data-poc", version=VERSION)

# ====== Schemas ======
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

class AskIn(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2
    lang: str = "ja"

class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

class ReindexIn(BaseModel):
    force: bool = True

# ====== Routes ======
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round(time.time() - START_TS, 2),
    }

@app.get("/")
def root():
    return {"ok": True, "service": "gov-data-poc", "version": VERSION}

# GET /ask（既存）
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., title="Q"),
    lang: str = Query("ja", title="Lang"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# ★ 追加: POST /ask
@app.post("/ask", response_model=AskResponse)
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(
        q=body.q,
        lang=body.lang,
        answer=f"[{body.lang}] 受理(POST): {body.q}",
        sources=[],
    )

# 既存: POST /feedback（./data/feedback に JSONL 出力）
@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    path = "./data/feedback"
    os.makedirs(path, exist_ok=True)
    out = os.path.join(path, f"{datetime.utcnow():%Y%m%d}.jsonl")

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": out})

# ★ 追加: POST /admin/reindex
@app.post("/admin/reindex")
def admin_reindex(
    body: ReindexIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)

    # フラグファイルで「再構築した」ことを記録
    flags_dir = "./data/flags"
    os.makedirs(flags_dir, exist_ok=True)
    flag_path = os.path.join(flags_dir, "reindexed.flag")
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.utcnow().isoformat() + "Z", "force": body.force}))

    return {"ok": True, "reindexed": True, "force": body.force, "flag": flag_path}
