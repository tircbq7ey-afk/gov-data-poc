# qa_service.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Body, Header
from pydantic import BaseModel, Field

app = FastAPI(title="gov-data-poc", version="dev")


# ====== Schemas ======
class AskResponse(BaseModel):
    q: str = Field(title="Q")
    lang: str = Field(title="Lang")
    answer: str = Field(title="Answer")
    sources: List[str] = Field(default_factory=list, title="Sources")


class AskGetQuery(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2
    lang: str = "ja"


class AskPostBody(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2
    lang: str = "ja"


class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"


class Health(BaseModel):
    ok: bool
    version: str
    build_time: str
    uptime_sec: float


# ====== Utilities ======
start_ts = datetime.utcnow()


def _dummy_answer(q: str, lang: str) -> str:
    # ここは暫定実装。後でRAGに置換予定
    if lang == "ja":
        return "[ja] 受理: " + q
    return "[en] received: " + q


# ====== Routes ======
@app.get("/health", response_model=Health, summary="Health")
def health() -> Health:
    return Health(
        ok=True,
        version="dev",
        build_time="unknown",
        uptime_sec=(datetime.utcnow() - start_ts).total_seconds(),
    )


@app.get("/", summary="Root")
def root():
    return {"ok": True}


# ---- /ask: GET（既存） ----
@app.get(
    "/ask",
    response_model=AskResponse,
    summary="Ask",
)
def ask_get(
    q: str,
    lang: str = "ja",
    top_k: int = 3,
    min_score: float = 0.2,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    # 認証が必要ならここで x_api_key を検証（現状はスキップ）
    answer = _dummy_answer(q, lang)
    return AskResponse(q=q, lang=lang, answer=answer, sources=[])


# ---- /ask: POST（新規追加） ----
@app.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask (POST)",
)
def ask_post(
    payload: AskPostBody = Body(...),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    # 認証が必要ならここで x_api_key を検証（現状はスキップ）
    answer = _dummy_answer(payload.q, payload.lang)
    return AskResponse(
        q=payload.q,
        lang=payload.lang,
        answer=answer,
        sources=[],
    )


# ---- /feedback: POST（既存維持）----
@app.post(
    "/feedback",
    summary="Feedback",
)
def feedback(
    fb: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    # 保存先: ./data/feedback/YYYYMMDD.jsonl
    out_dir = Path("./data/feedback")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (datetime.utcnow().strftime("%Y%m%d") + ".jsonl")

    # JSONL で追記保存
    import json

    rec = fb.model_dump()
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return {"ok": True, "path": str(out_path)}


# ---- /admin/reindex: POST（新規追加）----
@app.post("/admin/reindex", summary="Rebuild vector index")
def admin_reindex(
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """
    本番ではここで:
      - 既存インデックスの破棄/再構築
      - ドキュメントの再読み込み と 埋め込み計算
      - ベクターDBへ投入
    を行う。今はダミーで200を返す。
    """
    # TODO: 実装時に上記処理を追加
    return {"ok": True, "detail": "reindex started (dummy)"}
