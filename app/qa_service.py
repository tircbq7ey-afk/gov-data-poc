from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
import time
import re

app = FastAPI(title="gov-data-poc", version="0.1.0")

# ====== モデル ======
class AskRequest(BaseModel):
    q: str = Field(..., description="ユーザーの質問")
    top_k: int = Field(3, ge=1, le=20, description="返す件数")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="最低スコア")

class Source(BaseModel):
    title: str
    url: Optional[str] = None
    score: float
    snippet: Optional[str] = None

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[Source] = []

# ====== ユーティリティ ======
def detect_lang(text: str) -> str:
    # 非 ASCII が多ければ ja とみなすだけの簡易判定
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    return "ja" if non_ascii >= max(1, len(text) // 5) else "en"

def toy_ranker(q: str) -> List[Tuple[float, Source]]:
    """
    ダミー検索器: 質問に特定の単語が入っていれば、それっぽいソースを返す。
    次のステップで実データ検索に置換しやすいよう、(score, Source) のリストを返す。
    """
    hits: List[Tuple[float, Source]] = []
    text = q.lower()

    entries = [
        ("申請書の提出方法", "https://example.local/guide/submit", "窓口またはオンラインで提出できます。"),
        ("手数料", "https://example.local/fees", "各種手数料の一覧です。"),
        ("期限", "https://example.local/deadlines", "提出期限の説明です。")
    ]

    for title, url, snip in entries:
        # ゆるい一致（かな漢字と英数字を分けて検索）
        score = 0.0
        if any(k in text for k in ["申請", "提出", "method", "submit"]):
            score += 0.6
        if any(k in text for k in ["方法", "how", "guide"]):
            score += 0.3
        if title in q:
            score += 0.2
        if score > 0:
            hits.append((min(score, 1.0), Source(title=title, url=url, score=min(score, 1.0), snippet=snip)))

    # スコア降順
    hits.sort(key=lambda x: x[0], reverse=True)
    return hits

def build_answer(q: str, top_k: int, min_score: float) -> AskResponse:
    lang = detect_lang(q)
    ranked = toy_ranker(q)
    filtered = [src for sc, src in ranked if sc >= min_score][:top_k]

    if filtered:
        # ここでは一番上を要約っぽく返す簡易実装
        best = filtered[0]
        answer = best.snippet or best.title
    else:
        answer = "該当する情報が見つかりませんでした。"

    return AskResponse(q=q, lang=lang, answer=answer, sources=filtered)

# ====== ヘルスチェック ======
@app.get("/health")
def health():
    return {"ok": True, "version": app.version, "uptime_sec": 0}

# ====== /ask: GET ======
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="質問"),
    top_k: int = Query(3, ge=1, le=20),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
):
    return build_answer(q=q, top_k=top_k, min_score=min_score)

# ====== /ask: POST ======
@app.post("/ask", response_model=AskResponse)
def ask_post(body: AskRequest):
    return build_answer(q=body.q, top_k=body.top_k, min_score=body.min_score)
