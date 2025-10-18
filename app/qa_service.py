from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Body
from pydantic import BaseModel, Field


app = FastAPI(
    title="gov-data-poc",
    version="dev",
    description="Simple QA service (PoC) with GET/POST /ask and POST /feedback.",
)

# =========================
# Models
# =========================

class AskIn(BaseModel):
    q: str = Field(..., title="Question", description="User question (UTF-8)")
    top_k: int = Field(3, ge=1, le=50, description="Number of candidates")
    min_score: float = Field(0.2, ge=0.0, le=1.0, description="Similarity threshold")
    lang: str = Field("ja", description="Answer language code")

class Source(BaseModel):
    id: str = Field(..., title="Source ID")
    score: Optional[float] = Field(default=None, description="Optional score")

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[Source] = Field(default_factory=list)

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

class HealthResponse(BaseModel):
    ok: bool
    version: str
    build_time: str
    uptime_sec: float


# =========================
# Utilities (dummy search)
# =========================
def _dummy_answer(q: str, lang: str) -> AskResponse:
    """
    Replace this with your actual retriever/generator later.
    For now return a deterministic, safe dummy.
    """
    msg_ja = "（ダミー応答）オンラインで申請できます。"
    msg_en = "(dummy) You can apply online."
    answer = msg_ja if lang.startswith("ja") else msg_en
    return AskResponse(q=q, lang=lang, answer=answer, sources=[])


START_TIME = datetime.utcnow()


# =========================
# Endpoints
# =========================

@app.get("/health", response_model=HealthResponse, summary="Health")
def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        version="dev",
        build_time="unknown",
        uptime_sec=(datetime.utcnow() - START_TIME).total_seconds(),
    )


# --- ASK (GET) ---
@app.get(
    "/ask",
    response_model=AskResponse,
    summary="Ask",
)
def ask_get(
    q: str,
    top_k: int = 3,
    min_score: float = 0.2,
    lang: str = "ja",
) -> AskResponse:
    # NOTE: top_k, min_score は現状ダミー。後で検索ロジックに接続。
    return _dummy_answer(q=q, lang=lang)


# --- ASK (POST) ---
@app.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask (POST)",
)
def ask_post(payload: AskIn = Body(...)) -> AskResponse:
    # NOTE: payload.top_k / payload.min_score は現状ダミー
    return _dummy_answer(q=payload.q, lang=payload.lang)


# --- FEEDBACK (POST) ---
FEEDBACK_DIR = Path("./data/feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

@app.post(
    "/feedback",
    summary="Feedback",
    response_model=bool,
)
def feedback(payload: FeedbackIn) -> bool:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    # 日付別 JSONL に追記
    fname = FEEDBACK_DIR / (datetime.utcnow().strftime("%Y%m%d") + ".jsonl")
    rec = payload.model_dump()
    # 追記
    with fname.open("a", encoding="utf-8") as f:
        import json
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True


# --- ADMIN (reindex) ---
@app.post("/admin/reindex", summary="Trigger reindex")
def admin_reindex() -> dict:
    # 後で実装。現状はスタブで 200 を返す
    # 実装時はバックグラウンドでベクター化・インデックス更新などを実行
    return {"ok": True, "detail": "reindex queued (stub)"}
