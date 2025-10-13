from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

app = FastAPI(title="gov-data-poc", version="0.1.0")


class AskRequest(BaseModel):
    q: str = Field(..., description="検索クエリ")
    top_k: int = Field(5, ge=1, le=50, description="上位何件返すか")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="スコアの下限")


class Hit(BaseModel):
    lang: str
    answer: str
    sources: List[str]


class AskResponse(BaseModel):
    q: str
    took_ms: int
    hits: List[Hit]


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "version": "dev",
        "build_time": "unknown",
        "uptime_sec": 0,
    }


def _dummy_search(q: str, top_k: int, min_score: float) -> List[Hit]:
    # 実装差し替えポイント：今はダミー返却
    return [
        Hit(lang="ja", answer=f"「{q}」のダミー回答です。", sources=["dummy://source1", "dummy://source2"])
    ][: top_k]


@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="検索クエリ"),
    top_k: int = Query(5, ge=1, le=50),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
) -> AskResponse:
    start = datetime.now()
    hits = _dummy_search(q, top_k, min_score)
    took_ms = int((datetime.now() - start).total_seconds() * 1000)
    return AskResponse(q=q, took_ms=took_ms, hits=hits)


@app.post("/ask", response_model=AskResponse)
def ask_post(payload: AskRequest) -> AskResponse:
    start = datetime.now()
    hits = _dummy_search(payload.q, payload.top_k, payload.min_score)
    took_ms = int((datetime.now() - start).total_seconds() * 1000)
    return AskResponse(q=payload.q, took_ms=took_ms, hits=hits)
