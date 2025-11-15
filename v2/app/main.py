# app/main.py
from fastapi import FastAPI
from app.search import router as search_router

app = FastAPI(title="Gov Data API", version="2.0.0")

# ルーター登録
app.include_router(search_router)

@app.get("/")
def root():
    return {"message": "Gov Data API v2 running"}
