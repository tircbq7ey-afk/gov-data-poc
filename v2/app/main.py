import time
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 既存の Pydantic モデルを利用
from .models.schema import SearchRequest, FeedbackRequest, SearchResponse
from .service.feedback import save as feedback_save
from .util.metrics import track, p95

logger = logging.getLogger(__name__)

APP = FastAPI(title="VisaNavi API v2", version="0.2.0")

# CORS はそのままフル開放で
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@APP.get("/health")
def health():
    """簡単な健康チェック"""
    return {"status": "ok", "p95_ms": p95()}


@APP.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    """
    本番ロジックはまだ別途実装する前提で、
    まずは API が動いてレスポンスが返る状態を作る。
    """
    t0 = time.time()
    logger.info("search query=%r k=%s", req.query, getattr(req, "k", None))

    # ★暫定実装：とりあえず query をオウム返しするだけ
    answer = f"仮の検索APIです。query = '{req.query}' を受け取りました。"

    resp = SearchResponse(
        answer=answer,
        citations=[],   # まだベクター検索していないので空
        score=1.0,
    )

    # レイテンシ計測だけは動かしておく
    track((time.time() - t0) * 1000.0)
    return resp


@APP.post("/feedback")
def feedback(req: FeedbackRequest):
    """フィードバック保存は既存の実装を利用"""
    feedback_save(req)
    return {"status": "ok"}
