# qa_service.py
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse

app = FastAPI(title="gov-data-poc", version="dev")

# ====== 型 ======
from pydantic import BaseModel, Field


class AskQuery(BaseModel):
    q: str = Field(..., title="Query")
    lang: str = Field("ja", title="Lang")
    top_k: int = Field(3, ge=1, le=50, title="TopK")
    min_score: float = Field(0.2, ge=0.0, le=1.0, title="MinScore")


class Source(BaseModel):
    id: str = Field(..., title="Location")
    score: Optional[float] = None


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


# ====== 共通ロジック ======
def _answer_query(q: str, lang: str, top_k: int, min_score: float) -> AskResponse:
    """
    実データ検索の“入口”。まずはデモ実装：
    - 何もインデックスを持たない場合でも形だけ回答を返す
    - 後で RAG / ベクター検索に差し替えやすいように関数で分離
    """
    # TODO: ここに実データ検索を差し込む（ベクター検索・BM25など）
    demo_answer = "[ja] デモ回答: 実装済みの検索ロジックに置き換えてください。"
    return AskResponse(
        q=q,
        lang=lang,
        answer=demo_answer,
        sources=[],
    )


def _json(obj: BaseModel | dict) -> JSONResponse:
    # ensure_ascii=False で日本語の文字化けを最小化（表示側のエンコーディングにも依存）
    return JSONResponse(
        content=json.loads(json.dumps(obj if isinstance(obj, dict) else obj.model_dump(), ensure_ascii=False)),
        media_type="application/json; charset=utf-8",
    )


# ====== エンドポイント ======
@app.get("/health")
def health() -> JSONResponse:
    return _json(
        {
            "ok": True,
            "version": app.version,
            "build_time": "unknown",
            "uptime_sec": 0,  # 必要なら起動時刻から計算する
        }
    )


@app.get("/", summary="Root")
def root() -> JSONResponse:
    return _json({"ok": True, "service": app.title})


# ---- /ask: GET（既存の動作）----
@app.get("/ask", response_model=AskResponse, summary="Ask (GET)")
def ask_get(
    q: str,
    lang: str = "ja",
    top_k: int = 3,
    min_score: float = 0.2,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    return _answer_query(q=q, lang=lang, top_k=top_k, min_score=min_score)


# ---- /ask: POST（新規追加）----
@app.post("/ask", response_model=AskResponse, summary="Ask (POST)")
def ask_post(
    payload: AskQuery,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    return _answer_query(
        q=payload.q,
        lang=payload.lang,
        top_k=payload.top_k,
        min_score=payload.min_score,
    )


# ---- /feedback: POST（既存・jsonl に追記）----
@app.post("/feedback", response_model=FeedbackOut, summary="Feedback")
def feedback(
    fb: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    out_dir = Path("./data/feedback")
    out_dir.mkdir(parents=True, exist_ok=True)
    outfile = out_dir / f"{dt.datetime.utcnow():%Y%m%d}.jsonl"
    line = json.dumps(fb.model_dump(), ensure_ascii=False)
    with outfile.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return _json(FeedbackOut(ok=True, path=str(outfile)))


# ---- /admin/reindex: POST（スタブ実装）----
@app.post("/admin/reindex", summary="Rebuild index (stub)")
def admin_reindex(
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    # TODO: 実データの再取り込み＆インデックス構築をここに実装
    return _json({"ok": True, "indexed": 0})
