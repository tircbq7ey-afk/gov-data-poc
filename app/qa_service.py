# app/qa_service.py
from __future__ import annotations

from fastapi import FastAPI, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import datetime, timezone
import json
import os

app = FastAPI(
    title="gov-data-poc",
    version="dev",
)

DATA_DIR = Path("/app/data")
FEEDBACK_DIR = DATA_DIR / "feedback"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Schemas ----------
class AskResponse(BaseModel):
    q: str = Field(..., title="Q")
    lang: str = Field("ja", title="Lang")
    answer: str = Field("", title="Answer")
    sources: list[str] = Field(default_factory=list, title="Sources")


class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: list[str] = Field(default_factory=list)
    lang: str = "ja"


class FeedbackOut(BaseModel):
    ok: bool
    path: str


# ---------- Health ----------
@app.get("/health", summary="Health")
def health_health_get():
    return {
        "ok": True,
        "version": "dev",
        "build_time": "unknown",
        "uptime_sec": 0,  # ここは簡略化
    }


# ---------- Ask (GET) ----------
@app.get("/ask", summary="Ask", response_model=AskResponse)
def ask_ask_get(
    q: str = Query(..., description="user question"),
    lang: str = Query("ja"),
    top_k: int = Query(3, ge=1),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
):
    # 実データ検索のダミー応答（ここを後で実装に差し替え）
    answer = "[ja] 受理: " + q
    return AskResponse(q=q, lang=lang, answer=answer, sources=[])


# ---------- Ask (POST 同等挙動) ----------
class AskIn(BaseModel):
    q: str
    lang: str = "ja"
    top_k: int = 3
    min_score: float = 0.2

@app.post("/ask", summary="Ask (POST)", response_model=AskResponse)
def ask_ask_post(body: AskIn = Body(...)):
    # GET と同じロジックを使う
    return ask_ask_get(
        q=body.q,
        lang=body.lang,
        top_k=body.top_k,
        min_score=body.min_score,
    )


# ---------- Feedback (POST) ----------
@app.post("/feedback", summary="Feedback", response_model=FeedbackOut)
def feedback_feedback_post(
    fb: FeedbackIn = Body(...),
):
    # 日付ごとの jsonl に追記
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    day = datetime.now().strftime("%Y%m%d")
    out_path = FEEDBACK_DIR / f"{day}.jsonl"
    record = {
        "q": fb.q,
        "answer": fb.answer,
        "label": "good",                 # 必要ならクライアントで渡すよう拡張
        "sources": fb.sources,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return FeedbackOut(ok=True, path=str(out_path))


# ---------- Admin: Reindex (POST) ----------
@app.post("/admin/reindex", summary="Reindex dataset")
def admin_reindex_post():
    """
    ここでベクターインデックス再構築等を行う想定。
    いまはダミーで OK を返す。
    """
    # 実装例:
    # build_vector_index(source_dir="/app/data/raw", out_db="/app/data/db")
    return JSONResponse({"ok": True, "detail": "reindex started"})


# ---------- root ----------
@app.get("/", summary="Root")
def root_get():
    return {}
