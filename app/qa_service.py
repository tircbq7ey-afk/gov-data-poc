from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List

app = FastAPI(title="gov-data-poc", version="0.1.0")

# --------- Models ---------
class AskRequest(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = []

# --------- Health ---------
@app.get("/health")
def health():
    return {"ok": True, "version": "dev", "build_time": "unknown"}

# 共通実装
def _answer_core(q: str, top_k: int, min_score: float) -> AskResponse:
    # ここはダミー実装。後でベクタ検索に差し替えます
    ans = f"質問「{q}」に対するダミー回答です（top_k={top_k}, min_score={min_score}）。"
    return AskResponse(q=q, lang="ja", answer=ans, sources=[])

# --------- GET /ask ---------
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="質問文"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
):
    return _answer_core(q, top_k, min_score)

# --------- POST /ask ---------
@app.post("/ask", response_model=AskResponse)
def ask_post(req: AskRequest):
    return _answer_core(req.q, req.top_k, req.min_score)
