import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models.schema import SearchRequest, FeedbackRequest, SearchResponse
from .service.feedback import save as feedback_save
from .util.metrics import track, p95

APP = FastAPI(title="VisaNavi API", version="0.1.0")

APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@APP.get("/health")
def health():
    """ヘルスチェック用のエンドポイント"""
    return {"status": "ok", "p95_ms": p95()}


@APP.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    """
    検索 API（とりあえず疎通確認用のダミー実装）
    TODO: 後でベクターストア検索に差し替える
    """
    t0 = time.time()

    # 最小限のダミー応答
    resp = SearchResponse(
        answer="検索APIは疎通OKです（まだダミー実装）",
        citations={},
        score=1.0,
    )

    # レスポンスタイムを記録
    track((time.time() - t0) * 1000)
    return resp


@APP.post("/feedback")
def feedback(req: FeedbackRequest):
    """フィードバック保存用エンドポイント"""
    feedback_save(req)
    return {"status": "ok"}
