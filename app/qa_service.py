# qa_service.py — 完全版（lang切替/FAQキャッシュ優先/JSONL feedback/version付きhealth）
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
LOG_DIR = os.getenv("LOG_DIR", "./logs")

TEXTS_JSON = os.getenv("TEXTS_JSON", "./data/db/texts.json")
FAQ_JSON = os.getenv("FAQ_JSON", "./data/faq.json")
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.0"))
TOP_K_DEFAULT = int(os.getenv("TOP_K_DEFAULT", "5"))

VERSION = os.getenv("VERSION", "dev")
BUILD_SHA = os.getenv("BUILD_SHA", "local")
BUILD_TIME = os.getenv("BUILD_TIME", "")

# ========= logger =========
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ========= data load =========
def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("not found: %s", path)
        return default

def load_texts(path: str) -> List[Dict[str, Any]]:
    # expected: [{source_path,title,id,text,source_url}]
    return load_json(path, [])

def tokenize_for_bm25(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    toks = []
    for tok in text.split():
        toks.append(tok)
        for i in range(len(tok) - 1):
            toks.append(tok[i:i+2])
    return toks or list(text)

class HybridIndex:
    def __init__(self, docs: List[Dict[str, Any]]):
        self.docs = docs
        self.corpus = [d.get("text","") for d in docs]
        logger.info("docs=%d", len(self.docs))
        tokenized = [tokenize_for_bm25(t) for t in self.corpus]
        self.bm25 = BM25Okapi(tokenized)
        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2,3))
        self.tfidf = self.vectorizer.fit_transform(self.corpus)

    def _score_bm25(self, q: str) -> np.ndarray:
        return np.asarray(self.bm25.get_scores(tokenize_for_bm25(q)), dtype=float)

    def _score_vec(self, q: str) -> np.ndarray:
        qv = self.vectorizer.transform([q])
        return np.asarray(cosine_similarity(qv, self.tfidf)[0], dtype=float)

    def search(self, q: str, top_k=TOP_K_DEFAULT, bm25_top_n=50, w_bm25=0.55, w_vec=0.45, min_score=MIN_SCORE):
        if not self.docs: return []
        def norm(a):
            return (a - a.min())/ (a.max()-a.min()) if np.ptp(a)>0 else np.zeros_like(a)
        s_bm25 = self._score_bm25(q); s_vec = self._score_vec(q)
        mix = 0.55*norm(s_bm25) + 0.45*norm(s_vec)
        top_n_idx = np.argsort(s_bm25)[::-1][:bm25_top_n]
        selected = [(i, mix[i]) for i in top_n_idx if mix[i] >= float(min_score)]
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

# load indices
DOCS = load_texts(TEXTS_JSON)
INDEX = HybridIndex(DOCS)

def load_faq(path: str): return load_json(path, [])
FAQ_DEFAULT = load_faq(FAQ_JSON)               # 既定（.envのFAQ_JSON）
FAQ_MAP = {
    "ja": FAQ_DEFAULT,
    "vi": load_faq("./data/faq_vi.json"),
}

# ========= app =========
app = FastAPI(title="gov-data-poc")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

if os.path.exists("./static"):
    app.mount("/static", StaticFiles(directory="./static"), name="static")

@app.get("/")
def root():
    if os.path.exists("./static/index.html"):
        return RedirectResponse(url="/static/index.html", status_code=302)
    return JSONResponse({"ok": True, "message": "UI not bundled. Use the API."})

def assert_token(x_api_key: Optional[str]):
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ===== models =====
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
    label: Optional[str] = None      # "good" | "needs_improvement"
    verdict: Optional[str] = None    # alias
    sources: Optional[Union[List[str], str]] = None

# ===== endpoints =====
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": VERSION,
        "build_sha": BUILD_SHA,
        "build_time": BUILD_TIME,
        "index_exists": len(DOCS) > 0,
        "texts_exists": os.path.exists(TEXTS_JSON),
        "faq_exists": any(len(v)>0 for v in FAQ_MAP.values()),
        "min_score": MIN_SCORE,
        "top_k_default": TOP_K_DEFAULT,
    }

@app.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(...), top_k: int = Query(TOP_K_DEFAULT, ge=1, le=50),
    bm25_top_n: int = Query(50, ge=1, le=500),
    w_bm25: float = Query(0.55, ge=0.0, le=1.0),
    w_vec: float = Query(0.45, ge=0.0, le=1.0),
    min_score: float = Query(MIN_SCORE, ge=0.0, le=1.0),
    x_api_key: Optional[str] = Header(None),
):
    assert_token(x_api_key)
    res = INDEX.search(q, top_k=top_k, bm25_top_n=bm25_top_n, w_bm25=w_bm25, w_vec=w_vec, min_score=min_score)
    return {"ok": True, "results": res}

@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(..., description="質問/Câu hỏi"),
    lang: Optional[str] = Query(None, description="ja or vi"),
    top_k: int = Query(TOP_K_DEFAULT, ge=1, le=50),
    bm25_top_n: int = Query(50, ge=1, le=500),
    w_bm25: float = Query(0.55, ge=0.0, le=1.0),
    w_vec: float = Query(0.45, ge=0.0, le=1.0),
    min_score: float = Query(MIN_SCORE, ge=0.0, le=1.0),
    x_api_key: Optional[str] = Header(None),
):
    assert_token(x_api_key)

    # 0) 言語別FAQの選択
    faq = FAQ_MAP.get((lang or "").lower()) if lang else None
    if faq is None:
        faq = FAQ_DEFAULT

    # 1) FAQ（完全一致→部分一致）
    q_norm = (q or "").strip()
    faq_hit = None
    for item in faq:
        if q_norm == (item.get("q") or ""):
            faq_hit = item; break
    if not faq_hit:
        for item in faq:
            cand = (item.get("q") or "")
            if cand and (cand in q_norm or q_norm in cand):
                faq_hit = item; break
    if faq_hit:
        return {"ok": True, "answer": faq_hit.get("a",""), "results": [{"source_url": faq_hit.get("source",""), "text": faq_hit.get("a",""), "score": 1.0}]}

    # 2) 検索（DB）
    hits = INDEX.search(q, top_k=top_k, bm25_top_n=bm25_top_n, w_bm25=w_bm25, w_vec=w_vec, min_score=min_score)
    answer = hits[0]["text"] if hits else ""
    return {"ok": True, "answer": answer, "results": hits}

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
    assert_token(x_api_key)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload CSV with 'q' column")

    raw = await file.read()
    data = raw.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(data))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="empty CSV")
    norm_headers = [(h or "").strip().lstrip("\ufeff") for h in reader.fieldnames]
    reader.fieldnames = norm_headers
    lower_map = {h.lower(): h for h in reader.fieldnames}
    q_key = lower_map.get("q")
    if not q_key:
        raise HTTPException(status_code=400, detail="CSV needs column 'q'")

    out_rows = []
    for row in reader:
        query = (row.get(q_key) or "").strip()
        if not query:
            out_rows.append({"q": "", "answer": "", "sources": ""}); continue

        # FAQ first
        ans = ""; src = ""
        for item in FAQ_DEFAULT:  # バッチは既定言語（必要ならlang列対応に拡張）
            if query == (item.get("q") or "") or (item.get("q") or "") in query or query in (item.get("q") or ""):
                ans = item.get("a",""); src = item.get("source",""); break
        if ans:
            out_rows.append({"q": query, "answer": ans, "sources": src}); continue

        hits = INDEX.search(query, top_k=top_k, bm25_top_n=bm25_top_n, w_bm25=w_bm25, w_vec=w_vec, min_score=min_score)
        ans = hits[0]["text"] if hits else ""
        srcs = "; ".join([h.get("source_url") or h.get("source_path") or "" for h in hits])
        out_rows.append({"q": query, "answer": ans, "sources": srcs})

    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=["q","answer","sources"])
    writer.writeheader(); writer.writerows(out_rows)

    content = out.getvalue().encode("utf-8")
    ts = int(time.time()); tmp_path = os.path.join("/tmp", f"answers_{ts}.csv")
    with open(tmp_path, "wb") as f: f.write(content)
    return FileResponse(tmp_path, filename="answers.csv", media_type="text/csv")

@app.post("/feedback")
def feedback(payload: FeedbackIn = Body(...), request: Request = None, x_api_key: Optional[str] = Header(None)):
    assert_token(x_api_key)
    label = payload.label or payload.verdict or ""
    if label not in ("good", "needs_improvement"):
        raise HTTPException(status_code=400, detail="label must be 'good' or 'needs_improvement'")

    # sources normalize → list
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

    os.makedirs(LOG_DIR, exist_ok=True)
    fp = os.path.join(LOG_DIR, "feedback.jsonl")
    with open(fp, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True, "id": str(rec["ts"])}
