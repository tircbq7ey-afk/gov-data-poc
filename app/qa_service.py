# app/qa_service.py
from fastapi import FastAPI, Header
from pydantic import BaseModel
from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime
from rapidfuzz import process, fuzz
import csv
import json

APP_TITLE = "gov-data-poc"
APP_VERSION = "dev"

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

# --------- データ読み込み ---------
DATA_FILES = [Path("./answers.csv"), Path("./answers_A.csv")]
CorpusItem = Dict[str, str]
CORPUS: List[CorpusItem] = []

def _read_csv(path: Path) -> List[CorpusItem]:
    items: List[CorpusItem] = []
    if not path.exists():
        return items
    # Windows 環境でも安全にUTF-8(BOM可)で読む
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

load_corpus()

# 検索用キーのみの配列（性能最適化）
QUERIES = [item["q"] for item in CORPUS]

# --------- モデル ---------
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

# --------- ユーティリティ ---------
def search(q: str, top_k: int = 3, min_score: float = 0.2):
    """
    rapidfuzz のスコアは 0〜100 なので 0.0〜1.0 に正規化して比較
    """
    if not QUERIES:
        return []

    # token_set_ratio は語順に強い影響を受けにくい
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

# --------- エンドポイント ---------
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": APP_VERSION,
        "build_time": "unknown",
        "uptime_sec": 0,  # 簡略
    }

@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask_get(
    q: str,
    lang: Optional[str] = "ja",
    top_k: int = 3,
    min_score: float = 0.2,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    hits = search(q, top_k=top_k, min_score=min_score)
    if hits:
        best = hits[0]
        answer = best["a"]
        sources = [{"q": h["q"], "score": round(h["score"], 3), "source": h["source"]} for h in hits]
    else:
        answer = "すみません。該当する回答を見つけられませんでした。"
        sources = []

    return AskResponse(q=q, lang=lang or "ja", answer=answer, sources=sources)

@app.post("/feedback", summary="Feedback")
def feedback_post(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    out_dir = Path("./data/feedback")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{datetime.utcnow():%Y%m%d}.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(body.model_dump(), ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(out_path)}

# （任意）再インデックス
@app.post("/admin/reindex")
def admin_reindex():
    load_corpus()
    global QUERIES
    QUERIES[:] = [item["q"] for item in CORPUS]
    return {"ok": True, "size": len(CORPUS)}
