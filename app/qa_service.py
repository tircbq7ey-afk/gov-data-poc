# app/qa_service.py
from __future__ import annotations

from fastapi import FastAPI, Header
from pydantic import BaseModel
from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime, timezone
from rapidfuzz import process, fuzz
import csv
import json
import time

APP_TITLE = "gov-data-poc"
APP_VERSION = "dev"

app = FastAPI(title=APP_TITLE, version=APP_VERSION)
_app_started = time.time()

# ========= データ読み込み =========
DATA_FILES = [Path("./answers.csv"), Path("./answers_A.csv")]
CorpusItem = Dict[str, str]
CORPUS: List[CorpusItem] = []
QUERIES: List[str] = []  # 検索キーのみ

def _read_csv(path: Path) -> List[CorpusItem]:
    items: List[CorpusItem] = []
    if not path.exists():
        return items
    # Windows でも安全に UTF-8 (BOM 可) で読む
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = (row.get("q") or "").strip()
            a = (row.get("a") or "").strip()
            src = (row.get("source") or row.get("src") or path.name).strip()
            if q and a:
                items.append({"q": q, "a": a, "source": src})
    return items

def load_corpus() -> None:
    CORPUS.clear()
    for p in DATA_FILES:
        CORPUS.extend(_read_csv(p))
    QUERIES[:] = [item["q"] for item in CORPUS]

load_corpus()

# ========= スキーマ =========
class AskIn(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2
    lang: Optional[str] = "ja"

class AskResponse(BaseModel):
    q: str
    lang: str = "ja"
    answer: str
    sources: List[Dict[str, str]] = []

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = []
    lang: Optional[str] = "ja"

# ========= 検索ユーティリティ =========
def search(q: str, top_k: int = 3, min_score: float = 0.2):
    """
    rapidfuzz のスコアは 0〜100 なので 0.0〜1.0 に正規化して min_score と比較。
    """
    if not QUERIES or not q.strip():
        return []

    # 語順の影響が小さくノイズに強い scorer
    results = process.extract(
        q, QUERIES, scorer=fuzz.token_set_ratio, limit=max(top_k, 10)
    )

    hits = []
    for idx, score, _ in results:
        norm = float(score) / 100.0
        if norm >= min_score:
            item = CORPUS[idx]
            hits.append({
                "idx": idx,
                "score": norm,
                "q": item["q"],
                "a": item["a"],
                "source": item["source"],
            })
        if len(hits) >= top_k:
            break
    return hits

def build_answer(q: str, lang: Optional[str], top_k: int, min_score: float) -> AskResponse:
    hits = search(q, top_k=top_k, min_score=min_score)
    if hits:
        best = hits[0]
        answer = best["a"]
        sources = [{
            "q": h["q"],
            "score": round(h["score"], 3),
            "source": h["source"]
        } for h in hits]
    else:
        answer = "すみません。該当する回答を見つけられませんでした。"
        sources = []
    return AskResponse(q=q, lang=lang or "ja", answer=answer, sources=sources)

# ========= エンドポイント =========
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": APP_VERSION,
        "build_time": "unknown",
        "uptime_sec": round(time.time() - _app_started, 2),
    }

@app.get("/", summary="Root")
def root_get():
    return {"ok": True, "message": "gov-data-poc API"}

# ---- /ask (GET) ----
@app.get("/ask", response_model=AskResponse, summary="Ask (GET)")
def ask_get(
    q: str,
    lang: Optional[str] = "ja",
    top_k: int = 3,
    min_score: float = 0.2,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    return build_answer(q=q, lang=lang, top_k=top_k, min_score=min_score)

# ---- /ask (POST) ----
@app.post("/ask", response_model=AskResponse, summary="Ask (POST)")
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    return build_answer(q=body.q, lang=body.lang, top_k=body.top_k, min_score=body.min_score)

# ---- /feedback ----
@app.post("/feedback", summary="Feedback")
def feedback_post(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    out_dir = Path("./data/feedback")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{datetime.now(timezone.utc):%Y%m%d}.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(body.model_dump(), ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(out_path)}

# ---- （任意）再インデックス ----
@app.post("/admin/reindex", summary="Reindex corpus")
def admin_reindex():
    load_corpus()
    return {"ok": True, "size": len(CORPUS)}
