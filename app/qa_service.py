import os
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ====== メタ / 設定 ======
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

# 静的ファイルのルート（優先順: WEB_ROOT → ./index → ./）
_WEB_ROOT = os.getenv("WEB_ROOT", "").strip()
if _WEB_ROOT:
    WEB_ROOT = Path(_WEB_ROOT)
else:
    WEB_ROOT = Path("./index") if Path("./index/index.html").exists() else Path("./")

app = FastAPI(title="gov-data-poc", version=VERSION)


def _require(x_api_key: Optional[str]) -> None:
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


# ====== Health ======
@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round(time.time() - START_TS, 2),
    }


# ====== 型定義 ======
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)


class AskIn(BaseModel):
    q: str = Field(..., title="Q")
    lang: str = Field("ja", title="Lang")
    top_k: int | None = None
    min_score: float | None = None


class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"


# ====== /ask (GET) ======
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., title="Q"),
    lang: str = Query("ja", title="Lang"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # PoC のダミー応答
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])


# ====== /ask (POST) ======
@app.post("/ask", response_model=AskResponse)
def ask_post(
    payload: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(
        q=payload.q,
        lang=payload.lang,
        answer=f"[{payload.lang}] 受理: {payload.q}",
        sources=[],
    )


# ====== /feedback (POST) ======
@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)

    # ./data/feedback/YYYYMMDD.jsonl に追記
    base = Path("./data/feedback")
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"{datetime.utcnow():%Y%m%d}.jsonl"

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": str(out)})


# ====== /admin/reindex (POST) ======
@app.post("/admin/reindex")
def admin_reindex(
    payload: Dict[str, Any] = Body(default_factory=dict),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    """
    再インデックス・トリガ。
    data/flags にフラグファイルを置くだけの軽量実装。
    実処理は別プロセス/ジョブで拾う想定。
    """
    _require(x_api_key)

    flags_dir = Path("./data/flags")
    flags_dir.mkdir(parents=True, exist_ok=True)

    force = bool(payload.get("force", False))
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    flag_name = "reindex.force" if force else "reindex"
    flag_path = flags_dir / f"{flag_name}.{stamp}"

    with flag_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"force": force, "ts": stamp}, ensure_ascii=False))

    return JSONResponse({"ok": True, "path": str(flag_path)})


# ====== 静的ファイル配信（最後にマウントするのが重要） ======
# API でマッチしないパスはすべて WEB_ROOT から配信されます
#   例) /index.html, /favicon.ico, /assets/app.js など
app.mount("/", StaticFiles(directory=str(WEB_ROOT), html=True), name="site")
