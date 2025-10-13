from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="gov-data-poc", version="0.2.0")


# ==== 共通: 疎通 / 状態確認 ===============================================
@app.get("/health")
def health():
    return {"ok": True, "version": app.version}


# ==== モデル =============================================================
class AskRequest(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2


class AskResponse(BaseModel):
    hits: List[str]
    took_ms: int


# ==== ダミー検索ロジック（後で実データ検索に差し替え予定） ===============
def _search_stub(q: str, top_k: int, min_score: float) -> List[str]:
    """
    いまはスタブ。実データ検索に置き換える前提。
    - クエリを元に上位 top_k 件の文字列を返すだけ。
    """
    base = [
        f"answer for: {q}",
        f"suggestion 1 (min_score>={min_score})",
        f"suggestion 2 (top_k={top_k})",
        "see also: /faq",
    ]
    return base[: max(1, top_k)]


# ==== GET /ask（クエリストリング） ======================================
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="検索クエリ"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
):
    hits = _search_stub(q, top_k, min_score)
    return AskResponse(hits=hits, took_ms=1)


# ==== POST /ask（JSON ボディ） ==========================================
@app.post("/ask", response_model=AskResponse)
def ask_post(payload: AskRequest):
    hits = _search_stub(payload.q, payload.top_k, payload.min_score)
    return AskResponse(hits=hits, took_ms=1)


# ==== （ローカル実行用）==================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("qa_service:app", host="0.0.0.0", port=8010, reload=False)
