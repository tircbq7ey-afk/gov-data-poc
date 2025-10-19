# app/qa_service.py
import os, time, json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ========= Settings =========
API_TOKEN = os.getenv("API_TOKEN", "").strip()  # 例: changeme-local-token
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    """トークンが設定されているときだけ認証を有効化"""
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ========= Health / Root =========
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

# ========= /ask =========
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

# GET /ask（既存）
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(...),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # いまはダミー応答
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# POST /ask（追加）
class AskIn(BaseModel):
    q: str
    top_k: Optional[int] = 3
    min_score: Optional[float] = 0.2
    lang: str = "ja"

@app.post("/ask", response_model=AskResponse)
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # いまはダミー応答
    return AskResponse(
        q=body.q,
        lang=body.lang,
        answer=f"[{body.lang}] 受理: {body.q}",
        sources=[],
    )

# ========= /feedback =========
class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)

    out_dir = "./data/feedback"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{datetime.utcnow():%Y%m%d}.jsonl")

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": out_path})

# ========= /admin/reindex（追加） =========
class ReindexIn(BaseModel):
    force: bool = False

@app.post("/admin/reindex")
def admin_reindex(
    body: ReindexIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)

    flags_dir = "./data/flags"
    os.makedirs(flags_dir, exist_ok=True)
    marker = os.path.join(flags_dir, f"reindex_{datetime.utcnow():%Y%m%d%H%M%S}.flag")

    with open(marker, "w", encoding="utf-8") as f:
        f.write(json.dumps({"force": body.force, "ts": datetime.utcnow().isoformat() + "Z"}))

    return {"ok": True, "queued": True, "force": body.force, "flag": marker}
