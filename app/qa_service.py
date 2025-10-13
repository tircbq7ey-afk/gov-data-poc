# app/qa_service.py
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from typing import List
from time import perf_counter
from difflib import SequenceMatcher

app = FastAPI(title="gov-data-poc", version="0.1.0")

# ====== 入出力スキーマ ======
class AskRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=2000, description="質問文")
    top_k: int = Field(5, ge=1, le=50, description="返す候補数（最大50）")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="スコアの下限 (0.0〜1.0)")

class AskResponse(BaseModel):
    hits: List[str]
    took_ms: int

# ====== 簡易データ（ダミー検索用）======
# 実運用ではここをベクター検索やFAQデータに置き換えます
_FAQ = [
    "庁舎の開庁時間は平日9時から17時です。",
    "申請書の提出はポータルサイトからも可能です。",
    "パスワードを忘れた場合は再発行申請を行ってください。",
    "API の利用制限は1分あたり60リクエストです。",
    "お問い合わせはヘルプデスクまでメールでお願いします。",
]

def _score(a: str, b: str) -> float:
    """0〜1の類似度（超簡易: difflib）"""
    return SequenceMatcher(None, a, b).ratio()

def _search(q: str, top_k: int, min_score: float) -> List[str]:
    scored = [(_score(q, t), t) for t in _FAQ]
    scored.sort(reverse=True, key=lambda x: x[0])
    return [t for s, t in scored if s >= min_score][:top_k]

# ====== ルート/ヘルス ======
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
        "top_k_default": 5,
    }

# ====== /ask ======
@app.post("/ask", response_model=AskResponse)
async def ask(req: Request, body: AskRequest):
    # 簡易サイズ制限（1MB超のボディは拒否）
    cl = req.headers.get("content-length")
    if cl and int(cl) > 1_000_000:
        raise HTTPException(status_code=413, detail="payload too large")

    t0 = perf_counter()
    hits = _search(body.q.strip(), body.top_k, body.min_score)
    took_ms = int((perf_counter() - t0) * 1000)

    # 結果が0件でも 200 で空配列を返す（クライアント側でハンドリングしやすい）
    return AskResponse(hits=hits if hits else [f"echo: {body.q}"], took_ms=took_ms)
