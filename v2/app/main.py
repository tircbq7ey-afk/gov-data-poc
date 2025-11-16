# app/main.py

import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ★ 相対インポートで router だけ読み込む
from .service.search import router as search_router

APP = FastAPI(title="VisaNavi API", version="0.1.0")

APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@APP.get("/health")
def health():
    return {"status": "ok"}

# /search エンドポイントを有効化
APP.include_router(search_router)
