# qa_service.py
from __future__ import annotations
import os, glob, json, pickle
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Query, Header
from pydantic import BaseModel

# ---------------- Paths ----------------
DATA_DIR = Path(os.getenv("APP_DATA_DIR", "/app/data")).resolve()
RAW_DIR = DATA_DIR / "raw"
META_DIR = DATA_DIR / "meta"
FEEDBACK_DIR = DATA_DIR / "feedback"
INDEX_PATH = META_DIR / "tfidf_index.pkl"

for d in (RAW_DIR, META_DIR, FEEDBACK_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------- In-memory ----------------
_vectorizer = None      # sklearn TfidfVectorizer
_matrix = None          # scipy sparse matrix
_corpus: List[Dict[str, Any]] = []

def _has_index() -> bool:
    return INDEX_PATH.exists()

def _load_index() -> None:
    global _vectorizer, _matrix, _corpus
    if not _has_index():
        _vectorizer = None; _matrix = None; _corpus = []
        return
    with open(INDEX_PATH, "rb") as f:
        obj = pickle.load(f)
    _vectorizer = obj["vectorizer"]
    _matrix = obj["matrix"]
    _corpus = obj["corpus"]

def _save_index(vectorizer, matrix, corpus) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "wb") as f:
        pickle.dump({"vectorizer": vectorizer, "matrix": matrix, "corpus": corpus}, f)

# ---------------- Build index ----------------
def _collect_raw() -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []

    for p in glob.glob(str(RAW_DIR / "**/*.txt"), recursive=True):
        try:
            recs.append({"id": p, "text": Path(p).read_text(encoding="utf-8", errors="ignore"), "source": p})
        except Exception:
            pass

    for p in glob.glob(str(RAW_DIR / "**/*.jsonl"), recursive=True):
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for i, ln in enumerate(f, 1):
                    ln = ln.strip()
                    if not ln: continue
                    try:
                        obj = json.loads(ln)
                    except Exception:
                        continue
                    text = obj.get("text")
                    if not text:
                        q = obj.get("q") or obj.get("question") or ""
                        a = obj.get("a") or obj.get("answer") or ""
                        text = (q + "\n" + a).strip()
                    if text:
                        recs.append({"id": f"{p}#{i}", "text": text, "source": p})
        except Exception:
            pass
    return recs

def build_tfidf_index() -> int:
    from sklearn.feature_extraction.text import TfidfVectorizer
    recs = _collect_raw()
    if not recs:
        _save_index(None, None, [])
        return 0
    texts = [r["text"] for r in recs]
    vec = TfidfVectorizer(strip_accents="unicode", lowercase=True, ngram_range=(1, 2), max_df=0.95)
    mat = vec.fit_transform(texts)
    _save_index(vec, mat, recs)
    return len(recs)

def search(query: str, top_k: int, min_score: float):
    if not _vectorizer or _matrix is None or not _corpus:
        return []
    from sklearn.metrics.pairwise import cosine_similarity
    qv = _vectorizer.transform([query])
    sims = cosine_similarity(qv, _matrix).ravel()
    pairs = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)
    out = []
    for idx, score in pairs[: max(1, top_k)]:
        if score < min_score: continue
        rec = _corpus[idx]
        out.append({"score": float(score), "source": rec["source"], "snippet": rec["text"][:300]})
    return out

# ---------------- Schemas ----------------
class AskIn(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2
    lang: str = "ja"

class AskOut(BaseModel):
    q: str
    lang: str = "ja"
    answer: str = ""
    sources: list = []

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = []
    lang: str = "ja"

class FeedbackOut(BaseModel):
    ok: bool
    path: str

class ReindexOut(BaseModel):
    ok: bool
    indexed: int

# ---------------- App ----------------
app = FastAPI(title="gov-data-poc", version="dev")

@app.get("/health")
def health():
    return {"ok": True, "version": "dev", "build_time": "unknown"}

# Ask (GET)
@app.get("/ask", response_model=AskOut)
@app.get("/ask/", response_model=AskOut)
def ask_get(q: str = Query(...), top_k: int = 3, min_score: float = 0.2, lang: str = "ja",
            x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    return AskOut(q=q, lang=lang, answer="", sources=search(q, top_k, min_score))

# Ask (POST)
@app.post("/ask", response_model=AskOut)
@app.post("/ask/", response_model=AskOut)
def ask_post(payload: AskIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    return AskOut(q=payload.q, lang=payload.lang, answer="", sources=search(payload.q, payload.top_k, payload.min_score))

# Feedback (POST)
@app.post("/feedback", response_model=FeedbackOut)
@app.post("/feedback/", response_model=FeedbackOut)
def feedback_post(payload: FeedbackIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    # YYYYMMDD.jsonl に追記
    from datetime import datetime as _dt
    fname = FEEDBACK_DIR / f"{_dt.utcnow().strftime('%Y%m%d')}.jsonl"
    with open(fname, "a", encoding="utf-8") as f:
        f.write(json.dumps({"q": payload.q, "answer": payload.answer, "label": "good", "sources": payload.sources}, ensure_ascii=False) + "\n")
    return FeedbackOut(ok=True, path=str(fname.relative_to(Path.cwd())))

# Reindex (POST/GET どちらでもOK)
@app.post("/admin/reindex", response_model=ReindexOut)
@app.post("/admin/reindex/", response_model=ReindexOut)
@app.get("/admin/reindex", response_model=ReindexOut)
@app.get("/admin/reindex/", response_model=ReindexOut)
def admin_reindex(x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    count = build_tfidf_index()
    _load_index()
    return ReindexOut(ok=True, indexed=count)

# 起動時ロード
@app.on_event("startup")
def _startup():
    if _has_index():
        _load_index()
