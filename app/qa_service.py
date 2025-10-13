# qa_service.py
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import time

app = FastAPI(title="gov-data-poc", version="0.1.0")

# ----- models -----
class AskRequest(BaseModel):
    q: str = Field(..., description="質問文")
    top_k: int = Field(3, ge=1, le=50, description="最大ヒット件数")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="スコア閾値")

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str]
    took_ms: int

# ----- health -----
@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "version": os.getenv("VERSION", "dev"),
        "build_time": os.getenv("BUILD_TIME", "unknown"),
        "uptime_sec": float(os.getenv("UPTIME_SEC", "0")),
    }

# 共通ロジック（今はダミー。次の「実データ検索」でここを差し替え）
def _answer_core(q: str, top_k: int, min_score: float) -> AskResponse:
    t0 = time.time()
    # TODO: 実データ検索に置き換える
    dummy_sources = []
    ans = f"あなたの質問『{q}』に対するダミー回答です。（top_k={top_k}, min_score={min_score}）"
    took_ms = int((time.time() - t0) * 1000)
    return AskResponse(q=q, lang="ja", answer=ans, sources=dummy_sources, took_ms=took_ms)

# ----- GET /ask（クエリパラメータ） -----
@app.get("/ask", response_model=AskResponse, summary="質問（GET）")
def ask_get(
    q: str = Query(..., description="質問文"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="q is empty")
    return _answer_core(q, top_k, min_score)

# ----- POST /ask（JSON ボディ） -----
@app.post("/ask", response_model=AskResponse, summary="質問（POST）")
def ask_post(body: AskRequest):
    return _answer_core(body.q, body.top_k, body.min_score)
