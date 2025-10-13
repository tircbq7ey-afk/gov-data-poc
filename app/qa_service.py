# /app/qa_service.py
from __future__ import annotations

import os
import time
from typing import List, Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

APP_START_TS = time.time()
app = FastAPI(title="gov-data-poc", version="0.1.0")

def _env(name: str, default: str = "unknown") -> str:
    return os.getenv(name, default)

# ===== Schemas =====
class AskRequest(BaseModel):
    q: str = Field(..., description="ユーザの質問")
    top_k: int = Field(5, ge=1, le=50, description="返す最大件数")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="最低スコア（ダミー項目）")

class AskHit(BaseModel):
    text: str
    score: float

class AskResponse(BaseModel):
    hits: List[AskHit]
    took_ms: int

# ===== Health =====
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": _env("VERSION", "dev"),
        "build_time": _env("BUILD_TIME", "unknown"),
        "build_sha": _env("BUILD_SHA", "unknown"),
        "uptime_sec": round(time.time() - APP_START_TS, 2),
    }

# ===== ASK (POST/GET 両対応) =====
def _dummy_search(q: str, top_k: int) -> AskResponse:
    t0 = time.time()
    hits = [AskHit(text=f"{i+1}. {q}", score=max(0.0, 1.0 - i * 0.05)) for i in range(top_k)]
    return AskResponse(hits=hits, took_ms=int((time.time() - t0) * 1000))

@app.post("/ask", response_model=AskResponse)
def ask_post(body: AskRequest):
    return _dummy_search(body.q, body.top_k)

@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="ユーザの質問"),
    top_k: int = Query(5, ge=1, le=50),
    min_score: float = Query(0.0, ge=0.0, le=1.0),  # 将来用
):
    return _dummy_search(q, top_k)

@app.get("/")
def root():
    return {"service": "gov-data-poc", "endpoints": ["/health", "/ask"]}
