from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="gov-data-poc", version="0.1.0")

class AskRequest(BaseModel):
    q: str
    top_k: int = 5
    min_score: float = 0.0

class AskResponse(BaseModel):
    hits: List[str]
    took_ms: int

@app.get("/health")
def health():
    return {
        "ok": True,
        "version": app.version,
        "build_sha": "local",
        "build_time": "",
        "index_exists": True,
        "texts_exists": True,
        "faq_exists": True,
        "min_score": 0.0,
        "top_k_default": 5
    }

@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest):
    # 仮実装（後で検索やRAGに置換）
    return AskResponse(hits=[f"echo: {body.q}"], took_ms=1)
