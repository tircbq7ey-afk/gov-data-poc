# qa_service.py
from __future__ import annotations
import os
import glob
import json
import pickle
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Query, Header, HTTPException
from pydantic import BaseModel

# ====== 定数とパス ======
DATA_DIR = Path(os.getenv("APP_DATA_DIR", "/app/data")).resolve()
RAW_DIR = DATA_DIR / "raw"
META_DIR = DATA_DIR / "meta"
FEEDBACK_DIR = DATA_DIR / "feedback"
INDEX_PATH = META_DIR / "tfidf_index.pkl"

META_DIR.mkdir(parents=True, exist_ok=True)
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ====== 共有オブジェクト（遅延ロード） ======
_vectorizer = None   # sklearn.feature_extraction.text.TfidfVectorizer
_matrix = None       # scipy.sparse matrix
_corpus: List[Dict[str, Any]] = []  # [{'id':..., 'text':..., 'source':...}, ...]

def _has_index() -> bool:
    return INDEX_PATH.exists()

def _load_index() -> None:
    """起動時／reindex後に呼び出し。インデックスを読み込む。"""
    global _vectorizer, _matrix, _corpus
    if not _has_index():
        _vectorizer = None
        _matrix = None
        _corpus = []
        return
    with open(INDEX_PATH, "rb") as f:
        payload = pickle.load(f)
    _vectorizer = payload["vectorizer"]
    _matrix = payload["matrix"]
    _corpus = payload["corpus"]

def _save_index(vectorizer, matrix, corpus) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "wb") as f:
        pickle.dump({"vectorizer": vectorizer, "matrix": matrix, "corpus": corpus}, f)

# ====== インデックス作成 ======
def _yield_raw_records() -> List[Dict[str, Any]]:
    """
    ./data/raw 配下からデータを集約。
    - *.txt       : 1ファイル=1レコードとして text に格納
    - *.jsonl     : 1行ごとに JSON を読み、 text or (q + ' ' + a) を採用
    """
    records: List[Dict[str, Any]] = []

    # TXT
    for p in glob.glob(str(RAW_DIR / "**/*.txt"), recursive=True):
        try:
            text = Path(p).read_text(encoding="utf-8", errors="ignore")
            records.append({"id": p, "text": text, "source": p})
        except Exception:
            continue

    # JSONL（想定: {"q": "...", "a": "..."} または {"text": "..."}）
    for p in glob.glob(str(RAW_DIR / "**/*.jsonl"), recursive=True):
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for ln, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    text = obj.get("text")
                    if not text:
                        q = obj.get("q") or obj.get("question") or ""
                        a = obj.get("a") or obj.get("answer") or ""
                        text = f"{q}\n{a}".strip()
                    if text:
                        rec_id = f"{p}#{ln}"
                        records.append({"id": rec_id, "text": text, "source": p})
        except Exception:
            continue

    return records

def build_tfidf_index() -> Dict[str, Any]:
    """
    Scikit-learn の TF-IDF ベクトル化で全文検索用の疎行列を作成。
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS as EN_STOP

    records = _yield_raw_records()
    if not records:
        # 空でもインデックスファイルは空として保存しておく
        _save_index(None, None, [])
        return {"count": 0}

    corpus_texts = [r["text"] for r in records]
    vectorizer = TfidfVectorizer(
        strip_accents="unicode",
        lowercase=True,
        ngram_range=(1, 2),
        max_df=0.95,
        min_df=1,
        stop_words=None  # 日本語前提: ストップワードは未指定
    )
    matrix = vectorizer.fit_transform(corpus_texts)
    _save_index(vectorizer, matrix, records)
    return {"count": len(records)}

# ====== 検索 ======
def search_tfidf(query: str, top_k: int = 3, min_score: float = 0.2):
    """
    TF-IDF のコサイン類似度で上位抽出。min_score は 0〜1 のしきい値。
    """
    global _vectorizer, _matrix, _corpus
    if _vectorizer is None or _matrix is None or not _corpus:
        return []

    from sklearn.metrics.pairwise import cosine_similarity
    qv = _vectorizer.transform([query])
    sims = cosine_similarity(qv, _matrix).ravel()  # shape -> (N,)
    # スコアとインデックスをまとめて上位抽出
    pairs = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)
    results = []
    for idx, score in pairs[: max(top_k, 1)]:
        if score < min_score:
            continue
        rec = _corpus[idx]
        results.append(
            {
                "score": float(score),
                "source": rec["source"],
                "snippet": rec["text"][:300],
            }
        )
    return results

# ====== FastAPI 定義 ======
app = FastAPI(title="gov-data-poc", version="dev")

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

@app.get("/health")
def health():
    return {"ok": True, "version": "dev", "build_time": "unknown"}

# ------ Ask: GET（既存） ------
@app.get("/ask", response_model=AskOut, summary="Ask")
def ask_get(
    q: str = Query(..., title="Q"),
    lang: str = Query("ja", title="Lang"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    # 検索
    results = search_tfidf(q, top_k=3, min_score=0.2)
    answer = ""  # <- ここは生成要約を後で差し替え可能。今は空で返す。
    return AskOut(q=q, lang=lang, answer=answer, sources=results)

# ------ Ask: POST（新規） ------
@app.post("/ask", response_model=AskOut, summary="Ask (POST)")
def ask_post(
    payload: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    results = search_tfidf(payload.q, top_k=payload.top_k, min_score=payload.min_score)
    answer = ""  # 将来的にRAG応答へ拡張
    return AskOut(q=payload.q, lang=payload.lang, answer=answer, sources=results)

# ------ Feedback: POST（既存） ------
@app.post("/feedback", response_model=FeedbackOut, summary="Feedback")
def feedback_post(
    payload: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    fname = FEEDBACK_DIR / f"{Path.cwd().name}{Path.cwd().stat().st_mtime_ns}.jsonl"
    # 日付名のほうが良ければ下行を使う:
    # from datetime import datetime as _dt
    # fname = FEEDBACK_DIR / f"{_dt.utcnow().strftime('%Y%m%d')}.jsonl"

    line = {
        "q": payload.q,
        "answer": payload.answer,
        "label": "good",
        "sources": payload.sources,
    }
    # 追記
    with open(fname, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return FeedbackOut(ok=True, path=str(fname.relative_to(Path.cwd())))

# ------ Reindex: POST（新規） ------
@app.post("/admin/reindex", response_model=ReindexOut, summary="Rebuild TF-IDF index")
def admin_reindex(
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    info = build_tfidf_index()
    _load_index()
    return ReindexOut(ok=True, indexed=info.get("count", 0))

# 起動時にインデックスをロード
@app.on_event("startup")
def _on_startup():
    if _has_index():
        _load_index()
