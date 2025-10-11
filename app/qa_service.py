# app/qa_service.py — 完全版
import os
import json
import time
import logging
from typing import List, Dict, Any, Optional

from fastapi import (
    FastAPI, HTTPException, Query, Header, Request, Body
)
from fastapi.middleware.cors import CORSMiddleware
    # noqa: E402
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# 検索（軽量ライブラリ）
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

# ==========
# 設定
# ==========
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo ルート
DATA_DIR = os.path.join(BASE_DIR, "data")
FEEDBACK_DIR = os.path.join(DATA_DIR, "feedback")

FAQ_FILES = [
    os.path.join(DATA_DIR, "faq.json"),
    os.path.join(DATA_DIR, "faq_vi.json"),
]

load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=True)

API_TOKEN = os.getenv("API_TOKEN", "").strip()
APP_ENV = os.getenv("APP_ENV", "dev")
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "ja")

# ==========
# ロガー
# ==========
logging.basicConfig(
    level=logging.INFO if APP_ENV != "prod" else logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("qa_service")

# ==========
# データ読み込み
# ==========
class FaqItem(BaseModel):
    q: str
    a: str
    lang: str = "ja"
    tags: Optional[List[str]] = None
    id: Optional[str] = None

def _read_json(path: str) -> Optional[List[Dict[str, Any]]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_faqs() -> List[FaqItem]:
    items: List[FaqItem] = []
    for fp in FAQ_FILES:
        data = _read_json(fp)
        if not data:
            continue
        for i, row in enumerate(data):
            try:
                item = FaqItem(**row)
            except Exception:
                item = FaqItem(
                    q=row.get("q") or row.get("question", ""),
                    a=row.get("a") or row.get("answer", ""),
                    lang=row.get("lang", DEFAULT_LANG),
                    tags=row.get("tags"),
                    id=row.get("id") or f"{os.path.basename(fp)}#{i}",
                )
            items.append(item)
    return items

FAQS: List[FaqItem] = load_faqs()
if not FAQS:
    logger.warning("FAQ が 0 件です。data/faq*.json を確認してください。")

# ==========
# 索引の構築
# ==========
CORPUS = [f"{x.q}\n{x.a}" for x in FAQS]
BM25 = BM25Okapi([doc.split() for doc in CORPUS]) if CORPUS else None
VEC = TfidfVectorizer(norm="l2", ngram_range=(1, 2)) if CORPUS else None
TFIDF = VEC.fit_transform(CORPUS) if CORPUS else None

def search(query: str, lang: Optional[str] = None, k: int = 5) -> List[Dict[str, Any]]:
    if not CORPUS:
        return []
    bm_scores = BM25.get_scores(query.split()) if BM25 else [0.0] * len(CORPUS)
    tfidf_scores = (
        cosine_similarity(VEC.transform([query]), TFIDF).ravel().tolist()
        if TFIDF is not None else [0.0] * len(CORPUS)
    )
    scores = [0.6 * bm + 0.4 * tf for bm, tf in zip(bm_scores, tfidf_scores)]
    if lang:
        for i, item in enumerate(FAQS):
            if item.lang == lang:
                scores[i] *= 1.05
    idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    results = []
    for i in idx:
        item = FAQS[i]
        results.append(
            {
                "q": item.q,
                "a": item.a,
                "lang": item.lang,
                "score": round(float(scores[i]), 6),
                "source_id": item.id or f"faq#{i}",
            }
        )
    return results

# ==========
# FastAPI
# ==========
app = FastAPI(title="gov-data-poc QA Service", version="1.0.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(BASE_DIR, "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ==========
# モデル
# ==========
class AskResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]

class FeedbackPayload(BaseModel):
    q: Optional[str] = ""
    answer: Optional[str] = ""
    sources: Optional[List[Any]] = None
    label: Optional[str] = ""  # good / bad / comment
    note: Optional[str] = ""

# ==========
# 認証
# ==========
def require_token(x_api_key: Optional[str]):
    # トークン未設定ならスキップ（ローカル検証用）
    if not API_TOKEN:
        return
    if not x_api_key or x_api_key.strip() != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ==========
# ルーティング
# ==========
@app.get("/health")
def health():
    return {"ok": True, "items": len(FAQS)}

@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(..., description="質問文"),
    lang: str = Query(DEFAULT_LANG, description="クエリ言語"),
    x_api_key: Optional[str] = Header(None),
):
    require_token(x_api_key)
    candidates = search(q.strip(), lang=lang, k=5)
    if not candidates:
        return AskResponse(answer="すみません、該当が見つかりませんでした。", sources=[])
    top = candidates[0]
    return AskResponse(answer=top["a"], sources=candidates)

@app.post("/feedback")
def feedback(
    payload: FeedbackPayload = Body(...),
    request: Request = None,
    x_api_key: Optional[str] = Header(None),
):
    # 収集を無認可で許可したい場合は次行をコメントアウト
    require_token(x_api_key)

    label = (payload.label or "").lower()
    if label not in {"good", "bad", "comment", ""}:
        raise HTTPException(status_code=400, detail="invalid label")

    sources_list: List[Any] = []
    if payload.sources:
        for s in payload.sources[:5]:
            if isinstance(s, dict):
                sources_list.append({k: s.get(k) for k in ("source_id", "score")})
            else:
                sources_list.append(s)

    rec = {
        "ts": int(time.time()),
        "label": label,
        "q": payload.q or "",
        "answer": payload.answer or "",
        "sources": sources_list,
        "user_agent": request.headers.get("user-agent") if request else "",
    }

    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    fp = os.path.join(FEEDBACK_DIR, "feedback.jsonl")
    with open(fp, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return {"ok": True, "id": str(rec["ts"])}
