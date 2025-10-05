# app/qa_service.py — 完全版
import os, io, csv, json, time, logging
from typing import List, Dict, Any, Optional, Union

from fastapi import FastAPI, UploadFile, File, Query, Header, HTTPException, Body, Request
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

# ========= env =========
load_dotenv()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8010"))
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

TEXTS_JSON = os.getenv("TEXTS_JSON", "./data/db/texts.json")
FAQ_JSON = os.getenv("FAQ_JSON", "./data/faq.json")
FAQ_JSON_VI = os.getenv("FAQ_JSON_VI", "./data/faq_vi.json")
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.0"))
TOP_K_DEFAULT = int(os.getenv("TOP_K_DEFAULT", "5"))

# 保存先を /data/feedback（JSONL）
FEEDBACK_DIR = os.getenv("FEEDBACK_DIR", "./data/feedback")

VERSION = os.getenv("VERSION", "dev")
BUILD_SHA = os.getenv("BUILD_SHA", "local")
BUILD_TIME = os.getenv("BUILD_TIME", "")

# ========= logger =========
os.makedirs("./logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("./logs/app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ========= data =========
def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("not found: %s", path)
        return default

def _load_texts(path: str) -> List[Dict[str, Any]]:
    # [{source_path,title,id,text,source_url}] を想定
    return _read_json(path, [])

def _tokenize_for_bm25(s: str) -> List[str]:
    s = (s or "").strip()
    if not s: return []
    toks = []
    for t in s.split():
        toks.append(t)
        for i in range(len(t) - 1):
            toks.append(t[i:i+2])  # bi-gram 混ぜて言語非依存化
    return toks or list(s)

class HybridIndex:
    def __init__(self, docs: List[Dict[str, Any]]):
        self.docs = docs
        self.corpus = [d.get("text","") for d in docs]
        tokenized = [_tokenize_for_bm25(t) for t in self.corpus]
        self.bm25 = BM25Okapi(tokenized)
        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2,3))
        self.tfidf = self.vectorizer.fit_transform(self.corpus)
        logger.info("indexed docs=%d", len(self.docs))

    def _bm25(self, q: str) -> np.ndarray:
        return np.asarray(self.bm25.get_scores(_tokenize_for_bm25(q)), dtype=float)

    def _vec(self, q: str) -> np.ndarray:
        qv = self.vectorizer.transform([q])
        return np.asarray(cosine_similarity(qv, self.tfidf)[0], dtype=float)

    def search(self, q: str, top_k=TOP_K_DEFAULT, bm25_top_n=50, w_bm25=0.55, w_vec=0.45, min_score=MIN_SCORE):
        if not self.docs: return []
        def norm(a): return (a-a.min())/(a.max()-a.min()) if np.ptp(a)>0 else np.zeros_like(a)
        s_bm25 = self._bm25(q); s_vec = self._vec(q)
        mix = 0.55*norm(s_bm25)+0.45*norm(s_vec)
        cand = np.argsort(s_bm25)[::-1][:bm25_top_n]
        selected = [(i, mix[i]) for i in cand if mix[i] >= float(min_score)]
        selected.sort(key=lambda x: x[1], reverse=True)
        selected = selected[:top_k]
        out = []
        for i, score in selected:
            d = self.docs[i]
            out.append({
                "score": float(score),
                "title": d.get("title"),
                "id": d.get("id"),
                "text": d.get("text"),
                "source_path": d.get("source_path"),
                "source_url": d.get("source_url"),
            })
        return out

DOCS = _load_texts(TEXTS_JSON)
INDEX = HybridIndex(DOCS)

FAQ_JA = _read_json(FAQ_JSON, [])
FAQ_VI = _read_json(FAQ_JSON_VI, [])
FAQ_MAP = {"ja": FAQ_JA, "vi": FAQ_VI}

# ========= app =========
app = FastAPI(title="gov-data-poc")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if os.path.exists("./static"):
    app.mount("/static", StaticFiles(directory="./static"), name="static")

@app.get("/")
def root():
    if os.path.exists("./static/index.html"):
        return RedirectResponse(url="/static/index.html", status_code=302)
    return JSONResponse({"ok": True, "message": "UI not bundled. Use the API."})

def _assert_token(x_api_key: Optional[str]):
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

class SearchResponse(BaseModel):
    ok: bool
    results: List[Dict[str, Any]]

class AskResponse(BaseModel):
    ok: bool
    answer: str
    results: List[Dict[str, Any]]

class FeedbackIn(BaseModel):
    q: Optional[str] = ""
    answer: Optional[str] = ""
    label: Optional[str] = None  # "good" | "needs_improvement"
    verdict: Optional[str] = None  # alias
    sources: Optional[Union[List[str], str]] = None

@app.get("/health")
def health():
    return {
        "ok": True,
        "version": VERSION, "build_sha": BUILD_SHA, "build_time": BUILD_TIME,
        "index_exists": len(DOCS) > 0,
        "texts_exists": os.path.exists(TEXTS_JSON),
        "faq_exists": any(len(x)>0 for x in FAQ_MAP.values()),
        "min_score": MIN_SCORE, "top_k_default": TOP_K_DEFAULT,
    }

@app.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(...),
    top_k: int = Query(TOP_K_DEFAULT, ge=1, le=50),
    bm25_top_n: int = Query(50, ge=1, le=500),
    w_bm25: float = Query(0.55, ge=0.0, le=1.0),
    w_vec: float = Query(0.45, ge=0.0, le=1.0),
    min_score: float = Query(MIN_SCORE, ge=0.0, le=1.0),
    x_api_key: Optional[str] = Header(None),
):
    _assert_token(x_api_key)
    return {"ok": True, "results": INDEX.search(q, top_k, bm25_top_n, w_bm25, w_vec, min_score)}

@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(..., description="質問 / Câu hỏi"),
    lang: Optional[str] = Query(None, description="ja or vi"),
    top_k: int = Query(TOP_K_DEFAULT, ge=1, le=50),
    bm25_top_n: int = Query(50, ge=1, le=500),
    w_bm25: float = Query(0.55, ge=0.0, le=1.0),
    w_vec: float = Query(0.45, ge=0.0, le=1.0),
    min_score: float = Query(MIN_SCORE, ge=0.0, le=1.0),
    x_api_key: Optional[str] = Header(None),
):
    _assert_token(x_api_key)
    faq = FAQ_MAP.get((lang or "").lower()) or FAQ_JA
    qn = (q or "").strip()

    # 完全一致→部分一致でFAQ優先
    for item in faq:
        if qn == (item.get("q") or ""):
            return {"ok": True, "answer": item.get("a",""),
                    "results": [{"source_url": item.get("source",""), "text": item.get("a",""), "score": 1.0}]}
    for item in faq:
        cand = (item.get("q") or "")
        if cand and (cand in qn or qn in cand):
            return {"ok": True, "answer": item.get("a",""),
                    "results": [{"source_url": item.get("source",""), "text": item.get("a",""), "score": 0.9}]}

    hits = INDEX.search(q, top_k, bm25_top_n, w_bm25, w_vec, min_score)
    return {"ok": True, "answer": hits[0]["text"] if hits else "", "results": hits}

@app.post("/batch-ask")
async def batch_ask(
    file: UploadFile = File(...),
    top_k: int = Query(TOP_K_DEFAULT, ge=1, le=50),
    bm25_top_n: int = Query(50, ge=1, le=500),
    w_bm25: float = Query(0.55, ge=0.0, le=1.0),
    w_vec: float = Query(0.45, ge=0.0, le=1.0),
    min_score: float = Query(MIN_SCORE, ge=0.0, le=1.0),
    x_api_key: Optional[str] = Header(None),
):
    _assert_token(x_api_key)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload CSV with 'q' column")

    raw = await file.read()
    data = raw.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(data))
    if not reader.fieldnames: raise HTTPException(status_code=400, detail="empty CSV")

    # BOMや大文字小文字ゆれ対策
    reader.fieldnames = [(h or "").strip().lstrip("\ufeff") for h in reader.fieldnames]
    m = {h.lower(): h for h in reader.fieldnames}; key_q = m.get("q")
    if not key_q: raise HTTPException(status_code=400, detail="CSV needs column 'q'")

    rows = []
    for row in reader:
        query = (row.get(key_q) or "").strip()
        if not query: rows.append({"q":"", "answer":"", "sources":""}); continue

        # FAQ（日本語を既定）
        ans=""; src=""
        for item in FAQ_JA:
            qq = item.get("q") or ""
            if query == qq or qq in query or query in qq:
                ans = item.get("a",""); src = item.get("source",""); break
        if not ans:
            hits = INDEX.search(query, top_k, bm25_top_n, w_bm25, w_vec, min_score)
            ans = hits[0]["text"] if hits else ""
            src = "; ".join([h.get("source_url") or h.get("source_path") or "" for h in hits])

        rows.append({"q": query, "answer": ans, "sources": src})

    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=["q","answer","sources"])
    writer.writeheader(); writer.writerows(rows)
    tmp = os.path.join("/tmp", f"answers_{int(time.time())}.csv")
    with open(tmp, "wb") as f: f.write(out.getvalue().encode("utf-8"))
    return FileResponse(tmp, filename="answers.csv", media_type="text/csv")

@app.post("/feedback")
def feedback(payload: FeedbackIn = Body(...), request: Request = None, x_api_key: Optional[str] = Header(None)):
    _assert_token(x_api_key)
    label = payload.label or payload.verdict or ""
    if label not in ("good", "needs_improvement"):
        raise HTTPException(status_code=400, detail="label must be 'good' or 'needs_improvement'")

    # sources を配列に正規化
    if isinstance(payload.sources, list):
        sources_list = [s for s in payload.sources if s]
    elif isinstance(payload.sources, str):
        parts = []
        for sep in ["\n", ",", ";"]:
            for p in payload.sources.split(sep):
                p = p.strip()
                if p: parts.append(p)
        sources_list = parts
    else:
        sources_list = []

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
