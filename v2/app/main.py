# v2/app/main.py
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ← すべて相対インポートに統一
from .models.schema import SearchRequest, FeedbackRequest, SearchResponse
from .service.search import handle as search_handle, router as search_router
from .service.feedback import save as feedback_save
from .util.metrics import track, p95

APP = FastAPI(title="VisaNavi API", version="0.1.0")

APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターを登録（/search エンドポイント群）
APP.include_router(search_router)

@APP.get("/health")
def health():
    return {"status": "ok", "p95_ms": p95()}

@APP.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    t0 = time.time()
    resp = search_handle(req)
    track((time.time() - t0) * 1000)
    return resp

@APP.post("/feedback")
def feedback(req: FeedbackRequest):
    return feedback_save(req)
