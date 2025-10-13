from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import time

app = FastAPI(title="gov-data-poc", version="0.1.0")

START_TIME = time.time()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")

# ---------- Models ----------
class AskRequest(BaseModel):
    q: str = Field(..., description="質問文")
    top_k: int = Field(3, ge=1, le=50, description="候補件数")
    min_score: float = Field(0.2, ge=0.0, le=1.0, description="閾値")

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = []

# ---------- tiny demo search/answer ----------
def demo_answer(q: str, top_k: int, min_score: float) -> AskResponse:
    # ここは簡易ダミー実装。後で実データ検索に置き換え
    return AskResponse(
        q=q,
        lang="ja",
        answer=f"（デモ回答）質問='{q}', top_k={top_k}, min_score={min_score}",
        sources=[],
    )

# ---------- health ----------
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round(time.time() - START_TIME, 2),
    }

# ---------- /ask: GET（クエリパラメータ） ----------
@app.get("/ask", response_model=AskResponse, summary="Ask (GET)")
def ask_get(q: str, top_k: int = 3, min_score: float = 0.2):
    return demo_answer(q, top_k, min_score)

# ---------- /ask: POST（JSONボディ） ----------
@app.post("/ask", response_model=AskResponse, summary="Ask (POST)")
def ask_post(req: AskRequest):
    return demo_answer(req.q, req.top_k, req.min_score)
