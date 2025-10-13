from __future__ import annotations

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import List, Optional
import time
import csv
from pathlib import Path

app = FastAPI(title="gov-data-poc", version="0.1.0")

# ----------------------------
# モデル
# ----------------------------
class AskRequest(BaseModel):
    q: str = Field(..., description="検索クエリ")
    top_k: int = Field(5, ge=1, le=50, description="上位件数")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="最小スコア(0-1)")

class Hit(BaseModel):
    score: float
    answer: str
    source: Optional[str] = None

class AskResponse(BaseModel):
    hits: List[Hit]
    took_ms: int

# ----------------------------
# すごくシンプルな検索エンジン
# ----------------------------
_DATA: List[dict] = []

def _load_data_once() -> None:
    """data/ やリポジトリ直下にあるCSV(answers*.csv)をゆるく読む"""
    global _DATA
    if _DATA:
        return

    # 候補（存在するものだけ読む）
    candidates = [
        Path("data/answers.csv"),
        Path("data/answers_A.csv"),
        Path("answers.csv"),
        Path("answers_A.csv"),
    ]
    rows: List[dict] = []
    for p in candidates:
        if p.exists():
            with p.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    # 想定カラムが違ってもだいたい拾えるようにキー名をゆるく解決
                    text = r.get("answer") or r.get("text") or r.get("内容") or ""
                    src  = r.get("source") or r.get("url") or r.get("出典") or ""
                    if text:
                        rows.append({"answer": text, "source": src})
    # データが無いときはダミー
    if not rows:
        rows = [
            {"answer": "申請書は市役所窓口で提出できます。オンライン提出にも対応しています。", "source": "dummy:guide"},
            {"answer": "提出期限は毎月末日です。祝日の場合は翌開庁日。", "source": "dummy:deadline"},
            {"answer": "オンライン提出にはアカウント登録と本人確認が必要です。", "source": "dummy:online"},
        ]
    _DATA = rows

def _score(query: str, text: str) -> float:
    """雑なスコア: 部分一致 + トークン一致のハイブリッド（0..1）"""
    q = query.strip().lower()
    t = text.lower()
    if not q or not t:
        return 0.0
    base = 1.0 if q in t else 0.0
    qs = set(q.replace("　", " ").split())
    ts = set(t.replace("　", " ").split())
    if qs and ts:
        jacc = len(qs & ts) / len(qs | ts)
    else:
        jacc = 0.0
    # 部分一致に +α
    return min(1.0, base * 0.6 + jacc * 0.6)

def _search(query: str, top_k: int, min_score: float) -> List[Hit]:
    _load_data_once()
    scored = []
    for r in _DATA:
        s = _score(query, r["answer"])
        if s >= min_score:
            scored.append(Hit(score=round(s, 3), answer=r["answer"], source=r.get("source")))
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:top_k]

# ----------------------------
# ルーティング
# ----------------------------
@app.get("/health")
def health():
    """コンテナ内ヘルスチェック用"""
    return {"ok": True, "version": app.version}

@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="検索クエリ"),
    top_k: int = Query(5, ge=1, le=50),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
):
    """GET クエリ版"""
    t0 = time.perf_counter()
    hits = _search(q, top_k, min_score)
    took = int((time.perf_counter() - t0) * 1000)
    return AskResponse(hits=hits, took_ms=took)

@app.post("/ask", response_model=AskResponse)
def ask_post(body: AskRequest):
    """POST JSON 版"""
    t0 = time.perf_counter()
    hits = _search(body.q, body.top_k, body.min_score)
    took = int((time.perf_counter() - t0) * 1000)
    return AskResponse(hits=hits, took_ms=took)
