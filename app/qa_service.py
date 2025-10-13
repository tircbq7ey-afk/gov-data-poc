from typing import List, Optional
from fastapi import FastAPI, Query
from pydantic import BaseModel
import os
import time

app = FastAPI(title="gov-data-poc", version="0.1.0")
_start_ts = time.time()

# ---------------------------
# Models
# ---------------------------
class AskRequest(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = []

# ---------------------------
# Health
# ---------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": os.getenv("VERSION", "dev"),
        "build_time": os.getenv("BUILD_TIME", "unknown"),
        "uptime_sec": round(time.time() - _start_ts, 2),
    }

# ---------------------------
# Ask (implementation)
# ---------------------------
def _answer(req: AskRequest) -> AskResponse:
    # ここは後で「実データ検索」に差し替えます。今は疎通用の簡易実装。
    lang = "ja" if any("\u3040" <= ch <= "\u30ff" for ch in req.q) else "en"
    return AskResponse(
        q=req.q,
        lang=lang,
        answer=f"echo: {req.q} (top_k={req.top_k}, min_score={req.min_score})",
        sources=[]
    )

# GET /ask（クエリ文字列を受けて内部で共通処理へ）
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="Query text"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
):
    req = AskRequest(q=q, top_k=top_k, min_score=min_score)
    return _answer(req)

# POST /ask（JSON ボディを受ける本命）
@app.post("/ask", response_model=AskResponse)
def ask_post(body: AskRequest):
    return _answer(body)
