from fastapi import FastAPI, Body, Query
from pydantic import BaseModel
from typing import List, Optional
import os, time

APP_TITLE = "gov-data-poc"
APP_VERSION = "0.1.0"
START_TIME = time.time()

app = FastAPI(title=APP_TITLE, version=APP_VERSION)


# ===== Models =====
class AskRequest(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2
    lang: Optional[str] = None


class Source(BaseModel):
    title: str
    score: float
    url: Optional[str] = None


class AskHit(BaseModel):
    answer: str
    lang: str = "ja"
    sources: List[Source] = []


class AskResponse(BaseModel):
    q: str
    took_ms: int
    result: AskHit


# ===== Helpers =====
def _answer(q: str, top_k: int, min_score: float) -> AskResponse:
    t0 = time.time()
    # ここに本当の検索/生成処理を入れる。今はダミー応答。
    answer = f"質問「{q}」へのサンプル回答（top_k={top_k}, min_score={min_score}）。"
    return AskResponse(
        q=q,
        took_ms=int((time.time() - t0) * 1000),
        result=AskHit(answer=answer, lang="ja", sources=[]),
    )


# ===== Endpoints =====
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": os.getenv("VERSION", "dev"),
        "build_time": os.getenv("BUILD_TIME", "unknown"),
        "uptime_sec": round(time.time() - START_TIME, 2),
    }


@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="質問文"),
    top_k: int = Query(3, ge=1, le=100),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
):
    return _answer(q, top_k, min_score)


@app.post("/ask", response_model=AskResponse)
def ask_post(payload: AskRequest = Body(...)):
    return _answer(payload.q, payload.top_k, payload.min_score)
