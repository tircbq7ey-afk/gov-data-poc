# qa_service.py — 完全版（BOM対応 & フィードバックの入力ゆるく）

import os
import io
import csv
import json
import time
import logging
from typing import List, Dict, Any, Optional, Union

from fastapi import FastAPI, UploadFile, File, Query, Header, HTTPException, Body
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from dotenv import load_dotenv

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

# =============================================================================
# 環境変数
# =============================================================================
load_dotenv()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8010"))
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", "./logs")

TEXTS_JSON = os.getenv("TEXTS_JSON", "./data/db/texts.json")
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.0"))
TOP_K_DEFAULT = int(os.getenv("TOP_K_DEFAULT", "5"))

# =============================================================================
# ロガー
# =============================================================================
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

# =============================================================================
# データ読み込み & インデックス作成（BM25 + TF-IDF）
# =============================================================================
def load_texts(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        logger.warning("texts.json が見つかりません: %s", path)
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 期待スキーマ:
    # { "source_path": "...", "title": "...", "id": "...", "text": "...", "source_url": "..." }
    return data

def tokenize_for_bm25(text: str) -> List[str]:
    # 形態素解析なしの簡易トークナイザ（空白区切り + 2文字N-gram）
    text = text.strip()
    chunks: List[str] = []
    for tok in text.split():
        chunks.append(tok)
        for i in range(len(tok) - 1):
            chunks.append(tok[i:i+2])
    if not chunks and text:
        chunks = list(text)
    return chunks

class HybridIndex:
    def __init__(self, docs: List[Dict[str, Any]]):
        self.docs = docs
        self.corpus = [d.get("text", "") for d in docs]
        logger.info("docs=%d", len(self.docs))

        tokenized = [tokenize_for_bm25(t) for t in self.corpus]
        self.bm25 = BM25Okapi(tokenized)

        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 3))
        self.tfidf = self.vectorizer.fit_transform(self.corpus)

    def _score_bm25(self, q: str) -> np.ndarray:
        toks = tokenize_for_bm25(q)
        return np.asarray(self.bm25.get_scores(toks), dtype=float)

    def _score_vec(self, q: str) -> np.ndarray:
        qv = self.vectorizer.transform([q])
        sim = cosine_similarity(qv, self.tfidf)[0]
        return np.asarray(sim, dtype=float)

    def search(
        self,
        q: str,
        top_k: int = TOP_K_DEFAULT,
        bm25_top_n: int = 50,
        w_bm25: float = 0.55,
        w_vec: float = 0.45,
        min_score: float = MIN_SCORE,
    ) -> List[Dict[str, Any]]:
        if not self.docs:
            return []

        s_bm25 = self._score_bm25(q)
        s_vec = self._score_vec(q)

        # 正規化
        def norm(a: np.ndarray):
            if np.ptp(a) > 0:
                return (a - a.min()) / (a.max() - a.min())
            return np.zeros_like(a)

        s_bm25_n = norm(s_bm25)
        s_vec_n = norm(s_vec)
        mix = w_bm25 * s_bm25_n + w_vec * s_vec_n

        # BM25上位から候補抽出
        top_n_idx = np.argsort(s_bm25)[::-1][:bm25_top_n]
        selected = [(i, mix[i]) for i in top_n_idx if mix[i] >= float(min_score)]
        selected.sort(key=lambda x: x[1], reverse=True)
        selected = selected[:top_k]

        results: List[Dict[str, Any]] = []
        for idx, score in selected:
            d = self.docs[idx]
            results.append({
                "score": float(score),
                "title": d.get("title"),
                "id": d.get("id"),
                "text": d.get("text"),
                "source_path": d.get("source_path"),
                "source_url": d.get("source_url"),
            })
        return results

# =============================================================================
# FastAPI
# =============================================================================
app = FastAPI(title="gov-data-poc")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# /static 配信（UI）
if os.path.exists("./static"):
    app.mount("/static", StaticFiles(directory="./static"), name="static")

# / で UI を返す（Not Found を避ける）
@app.get("/")
def root():
    if os.path.exists("./static/index.html"):
        return RedirectResponse(url="/static/index.html", status_code=302)
    return JSONResponse({"ok": True, "message": "UI not bundled. Use the API."})

# インデックス初期化
DOCS = load_texts(TEXTS_JSON)
INDEX = HybridIndex(DOCS)

# 共通: API Key チェック
def assert_token(x_api_key: Optional[str]):
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ---- レスポンスモデル
class SearchResponse(BaseModel):
    ok: bool
    results: List[Dict[str, Any]]

class AskResponse(BaseModel):
    ok: bool
    answer: str
    results: List[Dict[str, Any]]

# =============================================================================
# Endpoints
# =============================================================================
@app.get("/health", response_model=Dict[str, Any])
def health(x_api_key: Optional[str] = Header(None)):
    # health は無認証でもOK。必要なら次行を有効化。
    # assert_token(x_api_key)
    return {
        "ok": True,
        "index_exists": len(DOCS) > 0,
        "texts_exists": os.path.exists(TEXTS_JSON),
        "bm25_exists": True,
        "min_score": MIN_SCORE,
        "top_k_default": TOP_K_DEFAULT,
    }

@app.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., description="検索クエリ"),
    top_k: int = Query(TOP_K_DEFAULT, ge=1, le=50),
    bm25_top_n: int = Query(50, ge=1, le=500),
    w_bm25: float = Query(0.55, ge=0.0, le=1.0),
    w_vec: float = Query(0.45, ge=0.0, le=1.0),
    min_score: float = Query(MIN_SCORE, ge=0.0, le=1.0),
    x_api_key: Optional[str] = Header(None),
):
    assert_token(x_api_key)
    res = INDEX.search(
        q, top_k=top_k, bm25_top_n=bm25_top_n, w_bm25=w_bm25, w_vec=w_vec, min_score=min_score
    )
    return {"ok": True, "results": res}

@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(..., description="質問"),
    top_k: int = Query(TOP_K_DEFAULT, ge=1, le=50),
    bm25_top_n: int = Query(50, ge=1, le=500),
    w_bm25: float = Query(0.55, ge=0.0, le=1.0),
    w_vec: float = Query(0.45, ge=0.0, le=1.0),
    min_score: float = Query(MIN_SCORE, ge=0.0, le=1.0),
    x_api_key: Optional[str] = Header(None),
):
    assert_token(x_api_key)
    hits = INDEX.search(
        q, top_k=top_k, bm25_top_n=bm25_top_n, w_bm25=w_bm25, w_vec=w_vec, min_score=min_score
    )
    answer = hits[0]["text"] if hits else ""
    return {"ok": True, "answer": answer, "results": hits}

# ----------------------- CSV バッチ質問（BOM対応） ----------------------------
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
        raise HTTPException(status_code=400, detail="CSV をアップロードしてください（列名: q）")

    # ★ Excel 由来の BOM 付き UTF-8 でも OK にする
    raw = await file.read()
    data = raw.decode("utf-8-sig", errors="ignore")  # ← ここが肝

    reader = csv.DictReader(io.StringIO(data))
    # ヘッダを正規化（BOM/空白/大文字小文字）
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="空のCSVです")
    norm_headers = [(h or "").strip().lstrip("\ufeff") for h in reader.fieldnames]
    reader.fieldnames = norm_headers
    lower_map = {h.lower(): h for h in reader.fieldnames}
    q_key = lower_map.get("q")
    if not q_key:
        raise HTTPException(status_code=400, detail="CSV に 'q' 列が必要です")

    out_rows = []
    for row in reader:
        q = (row.get(q_key) or "").strip()
        if not q:
            out_rows.append({"q": "", "answer": "", "sources": ""})
            continue
        hits = INDEX.search(
            q, top_k=top_k, bm25_top_n=bm25_top_n, w_bm25=w_bm25, w_vec=w_vec, min_score=min_score
        )
        ans = hits[0]["text"] if hits else ""
        srcs = "; ".join([h.get("source_url") or h.get("source_path") or "" for h in hits])
        out_rows.append({"q": q, "answer": ans, "sources": srcs})

    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=["q", "answer", "sources"])
    writer.writeheader()
    writer.writerows(out_rows)

    content = out.getvalue().encode("utf-8")
    ts = int(time.time())
    tmp_path = os.path.join("/tmp", f"answers_{ts}.csv")
    with open(tmp_path, "wb") as f:
        f.write(content)
    return FileResponse(tmp_path, filename="answers.csv", media_type="text/csv")

# ----------------------- UI フィードバック（入力ゆるく） ----------------------
class FeedbackIn(BaseModel):
    q: Optional[str] = ""
    answer: Optional[str] = ""
    # クライアント都合で "label" または "verdict" のどちらかが来る
    label: Optional[str] = None
    verdict: Optional[str] = None
    # 配列でも文字列でもOK（後で正規化）
    sources: Optional[Union[List[str], str]] = None

@app.post("/feedback")
def feedback(payload: FeedbackIn = Body(...), x_api_key: Optional[str] = Header(None)):
    """UI のフィードバックを CSV に追記して ok=True を返す"""
    assert_token(x_api_key)

    label = payload.label or payload.verdict or ""
    if label not in ("good", "needs_improvement"):
        raise HTTPException(status_code=400, detail="label must be 'good' or 'needs_improvement'")

    # sources を統一的に文字列へ
    if isinstance(payload.sources, list):
        sources_joined = "; ".join([s for s in payload.sources if s])
    elif isinstance(payload.sources, str):
        # 改行・カンマ・セミコロン区切りのどれでもだいたい OK
        parts = [p.strip() for sep in ["\n", ",", ";"] for p in payload.sources.split(sep)]
        sources_joined = "; ".join([p for p in parts if p])
    else:
        sources_joined = ""

    fb_path = os.path.join(LOG_DIR, "feedback.csv")
    new_file = not os.path.exists(fb_path)
    with open(fb_path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["ts", "label", "q", "answer", "sources"])
        w.writerow([
            int(time.time()),
            label,
            payload.q or "",
            payload.answer or "",
            sources_joined,
        ])
    return {"ok": True}
