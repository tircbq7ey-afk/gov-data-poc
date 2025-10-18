from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json

app = FastAPI(title="gov-data-poc", version="dev")

# =========================
# Models
# =========================
class AskIn(BaseModel):
    q: str = Field(..., title="Q")
    top_k: int = 3
    min_score: float = 0.2
    lang: str = "ja"

class Source(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    score: Optional[float] = None
    snippet: Optional[str] = None

class AskResponse(BaseModel):
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

class Health(BaseModel):
    ok: bool
    version: str
    build_time: str
    uptime_sec: float

# =========================
# In-memory / stub storage
# =========================
APP_START = datetime.utcnow()
DATA_DIR = Path("./data")
FEEDBACK_DIR = DATA_DIR / "feedback"
DOCS_DIR = DATA_DIR / "documents"
INDEX_DIR = DATA_DIR / "index"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# ダミーの検索器（必要に応じて本実装に置換）
def search_stub(q: str, top_k: int, min_score: float) -> List[Source]:
    # TODO: ベクタ検索に置き換え
    return []

def answer_stub(q: str, hits: List[Source], lang: str) -> str:
    # TODO: LLM 連携に置き換え
    return "[ja] 受理: 申請書の提出方法"

# =========================
# Endpoints
# =========================
@app.get("/health", response_model=Health, summary="Health")
def health() -> Health:
    return Health(
        ok=True,
        version="dev",
        build_time="unknown",
        uptime_sec=(datetime.utcnow() - APP_START).total_seconds(),
    )

@app.get("/", summary="Root")
def root() -> Dict[str, Any]:
    return {"ok": True}

# ---- /ask: GET（既存互換） ----
@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask_get(
    q: str,
    lang: str = "ja",
    top_k: int = 3,
    min_score: float = 0.2,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    hits = search_stub(q, top_k, min_score)
    ans = answer_stub(q, hits, lang)
    return AskResponse(q=q, lang=lang, answer=ans, sources=hits)

# ---- /ask: POST（新規追加） ----
@app.post("/ask", response_model=AskResponse, summary="Ask (POST)")
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    hits = search_stub(body.q, body.top_k, body.min_score)
    ans = answer_stub(body.q, hits, body.lang)
    return AskResponse(q=body.q, lang=body.lang, answer=ans, sources=hits)

# ---- /feedback: POST（既存） ----
@app.post("/feedback", response_model=FeedbackOut, summary="Feedback")
def feedback(
    fb: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    ts = datetime.utcnow().strftime("%Y%m%d")
    out = FEEDBACK_DIR / f"{ts}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fb.model_dump(), ensure_ascii=False) + "\n")
    return FeedbackOut(ok=True, path=str(out))

# ---- /admin/reindex: POST（新規追加）----
@app.post("/admin/reindex", summary="Rebuild index")
def admin_reindex(
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
) -> Dict[str, Any]:
    # TODO: 実データから埋め込みを作って INDEX_DIR に保存する処理を書く
    # ここではスタブで空のインデックスを作るだけ
    (INDEX_DIR / "READY").write_text(datetime.utcnow().isoformat(), encoding="utf-8")
    return {"ok": True, "indexed_docs": 0, "index_dir": str(INDEX_DIR)}
