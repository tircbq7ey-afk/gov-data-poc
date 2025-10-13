from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional
import os
import time

APP_VERSION = os.getenv("VERSION", "dev")
START_AT = time.time()

app = FastAPI(title="gov-data-poc", version="0.1.0")


# ----- models -----
class AskRequest(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2


class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str]


# ----- helpers -----
def _detect_lang(text: str) -> str:
    # 超簡易判定: 日本語っぽいコードポイントが混ざっていたら 'ja'
    return "ja" if any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in text) else "en"


def _answer(req: AskRequest) -> AskResponse:
    # ここは後で実データ検索ロジックに差し替える想定
    lang = _detect_lang(req.q)
    msg = "これはデモ応答です（実データ検索は未実装）。" if lang == "ja" else "This is a demo answer (search not wired yet)."
    return AskResponse(q=req.q, lang=lang, answer=msg, sources=[])


# ----- health -----
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": APP_VERSION,
        "build_time": os.getenv("BUILD_TIME", "unknown"),
        "uptime_sec": round(time.time() - START_AT, 2),
    }


# ----- ask (GET) -----
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="query"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
):
    req = AskRequest(q=q, top_k=top_k, min_score=min_score)
    return _answer(req)


# ----- ask (POST) -----
@app.post("/ask", response_model=AskResponse)
def ask_post(payload: AskRequest):
    return _answer(payload)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("qa_service:app", host="0.0.0.0", port=8010)
