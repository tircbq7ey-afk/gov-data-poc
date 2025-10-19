import os
import time
import json
from datetime import datetime
from typing import Optional, List, Any, Dict

from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ------------------------------------------------------------
# Settings
# ------------------------------------------------------------
API_TOKEN = os.getenv("API_TOKEN", "").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

def _require(x_api_key: Optional[str]) -> None:
    """Require x-api-key only when API_TOKEN is set."""
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ------------------------------------------------------------
# Pydantic models
# ------------------------------------------------------------
class AskOut(BaseModel):
    q: str
    lang: str = "ja"
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
    force: bool = False

# ------------------------------------------------------------
# FastAPI
# ------------------------------------------------------------
app = FastAPI(title="gov-data-poc", version=VERSION)

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

# ------------------------ /ask ------------------------------

def _dummy_answer(q: str, lang: str) -> str:
    # PoC用ダミー。実データ検索に繋ぐ場合はここを差し替え
    return f"[{lang}] 受理: {q}" if lang.startswith("ja") else f"[{lang}] accepted: {q}"

@app.get("/ask", response_model=AskOut)
def ask_get(
    q: str = Query(..., description="ユーザ質問"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.2, ge=0, le=1),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    answer = _dummy_answer(q, lang)
    return AskOut(q=q, lang=lang, answer=answer, sources=[])

@app.post("/ask", response_model=AskOut)
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    answer = _dummy_answer(body.q, body.lang)
    return AskOut(q=body.q, lang=body.lang, answer=answer, sources=[])

# ---------------------- /feedback ---------------------------

FEEDBACK_DIR = "/app/data/feedback"  # ホストの ./data にマウント

@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    out_path = os.path.join(FEEDBACK_DIR, f"{datetime.utcnow():%Y%m%d}.jsonl")

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": out_path})

# ---------------------- /admin/reindex ----------------------

@app.post("/admin/reindex")
def admin_reindex(
    body: ReindexIn = ReindexIn(),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # 実処理に差し替え可（PoCではダミー）
    return {"ok": True, "reindexed": True, "force": body.force}
