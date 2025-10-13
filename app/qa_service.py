# qa_service.py  — complete version with GET and POST /ask
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional
import time

app = FastAPI(title="gov-data-poc", version="0.1.0")


# ======== Models ========
class AskRequest(BaseModel):
    q: str = Field(..., description="ユーザーの質問")
    top_k: int = Field(5, ge=1, le=50, description="最大ヒット件数")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="スコアの下限")

class AskResponse(BaseModel):
    hits: List[str]
    took_ms: int


# ======== Endpoints ========
@app.get("/health")
def health():
    return {"ok": True, "version": app.version}

# GET /ask (クエリ文字列)
@app.get("/ask", response_model=AskResponse)
def ask_get(q: str, top_k: int = 5, min_score: float = 0.0):
    started = time.perf_counter()
    # TODO: 実検索ロジックに差し替え
    results = [f"echo: {q} (#{i+1})" for i in range(top_k)]
    took = int((time.perf_counter() - started) * 1000)
    return AskResponse(hits=results, took_ms=took)

# POST /ask (JSON ボディ)
@app.post("/ask", response_model=AskResponse)
def ask_post(req: AskRequest):
    started = time.perf_counter()
    # TODO: 実検索ロジックに差し替え
    results = [f"echo: {req.q} (#{i+1})" for i in range(req.top_k)]
    took = int((time.perf_counter() - started) * 1000)
    return AskResponse(hits=results, took_ms=took)


# uvicorn は Dockerfile の CMD から起動される想定
# もしローカル実行したい場合は以下を使用:
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("qa_service:app", host="0.0.0.0", port=8010, reload=True)
