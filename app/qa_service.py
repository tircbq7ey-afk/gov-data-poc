# qa_service.py
from fastapi import FastAPI, Header, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json

app = FastAPI(
    title="gov-data-poc",
    version="dev",
    openapi_url="/openapi.json",
)

# ====== Pydantic models ======

class AskIn(BaseModel):
    q: str = Field(..., title="質問")
    top_k: int = Field(3, ge=1, le=50, title="Top K")
    min_score: float = Field(0.2, ge=0, le=1, title="Min Score")
    lang: str = Field("ja", title="Lang")

class Source(BaseModel):
    title: str
    url: Optional[str] = None
    score: Optional[float] = None

class AskOut(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[Source] = []

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = []
    lang: str = "ja"

class FeedbackOut(BaseModel):
    ok: bool
    path: str

class ReindexOut(BaseModel):
    ok: bool
    indexed_docs: int
    msg: str = ""

# ====== Helpers ======

def _dummy_answer(q: str, lang: str) -> str:
    # ここに実検索ロジック（RAG 等）を入れる想定。
    # ひとまずダミー回答。
    if lang.startswith("ja"):
        return "[ja] 受理: " + q
    return "[en] accepted: " + q

def _feedback_path() -> Path:
    d = Path("./data/feedback")
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{datetime.utcnow():%Y%m%d}.jsonl"

# ====== Endpoints ======

@app.get("/health")
def health():
    return {"ok": True, "version": "dev", "build_time": "unknown", "uptime_sec": 0}

# --- Ask (GET) 既存 ---
@app.get("/ask", response_model=AskOut, summary="Ask")
def ask_get(
    q: str = Query(..., title="q"),
    lang: str = Query("ja", title="Lang"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.2, ge=0, le=1),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    answer = _dummy_answer(q, lang)
    return AskOut(q=q, lang=lang, answer=answer, sources=[])

# --- Ask (POST) 新規 ---
@app.post("/ask", response_model=AskOut, summary="Ask (POST)")
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    answer = _dummy_answer(body.q, body.lang)
    return AskOut(q=body.q, lang=body.lang, answer=answer, sources=[])

# --- Feedback (POST) 既存 ---
@app.post("/feedback", response_model=FeedbackOut, summary="Feedback")
def feedback_feedback_post(
    fb: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    path = _feedback_path()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fb.dict(), ensure_ascii=False) + "\n")
    return FeedbackOut(ok=True, path=str(path))

# --- Reindex (POST) 新規（簡易） ---
@app.post("/admin/reindex", response_model=ReindexOut, summary="Reindex")
def admin_reindex_post(
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """
    本番ではここでドキュメントを読み込み、ベクター索引を再構築する。
    ここでは docs 配下のファイル数を数えるダミー実装。
    """
    docs_dir = Path("./data/docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    count = sum(1 for _ in docs_dir.rglob("*") if _.is_file())
    return ReindexOut(ok=True, indexed_docs=count, msg="Reindexed (dummy)")
