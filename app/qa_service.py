# /app/qa_service.py
from __future__ import annotations

import os
import time
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

APP_START_TS = time.time()

def _env(name: str, default: str = "unknown") -> str:
    return os.getenv(name, default)

app = FastAPI(title="gov-data-poc", version="0.1.0")

# ====== Schemas ======
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

# ====== Health ======
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": _env("VERSION", "dev"),
        "build_time": _env("BUILD_TIME", "unknown"),
        "build_sha": _env("BUILD_SHA", "unknown"),
        "uptime_sec": round(time.time() - APP_START_TS, 2),
    }

# ====== ASK ======
@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest):
    """
    シンプルなダミー実装：
    - 実検索の代わりに、問い合わせ文をそのまま top_k 回返す
    - スコアは 1.0 から降順にダミー値
    将来、RAG/ベクタ検索などの本実装に差し替え予定
    """
    t0 = time.time()

    # ここで本来は検索などを実行する
    k = body.top_k
    # ダミーヒットを生成
    hits = [
        AskHit(text=f"{i+1}. {body.q}", score=max(0.0, 1.0 - i * 0.05))
        for i in range(k)
    ]

    took_ms = int((time.time() - t0) * 1000)
    return AskResponse(hits=hits, took_ms=took_ms)

# 任意：トップページ
@app.get("/")
def root():
    return {"service": "gov-data-poc", "endpoints": ["/health", "/ask"]}
