# v2/app/main.py
from fastapi import FastAPI

from app.models.schema import SearchRequest, FeedbackRequest
from app.service.search import handle as search_handle
from app.service.feedback import handle as feedback_handle

APP = FastAPI()


@APP.get("/health")
async def health():
    return {"status": "ok"}


@APP.post("/search")
async def search(req: SearchRequest):
    """
    ベクタ検索 API。
    戻り値は service.search.handle の JSON をそのまま返します。
    """
    return search_handle(req)


@APP.post("/feedback")
async def feedback(req: FeedbackRequest):
    """
    フィードバック API（こちらは従来通りで OK）。
    """
    return feedback_handle(req)
