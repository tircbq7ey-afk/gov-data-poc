from __future__ import annotations
from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Tuple
from pathlib import Path
from datetime import datetime
import csv
import difflib
import json
import os

app = FastAPI(title="gov-data-poc", version="dev")

# =========
# モデル
# =========
class AskResponse(BaseModel):
    q: str
    lang: str = "ja"
    answer: str
    sources: List[str] = []

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = []
    lang: str = "ja"


# =========
# 簡易インデックス
# =========
INDEX: List[Dict[str, str]] = []  # dict: {"q":..., "a":..., "source":...}

QUESTION_KEYS = ("q", "question", "query", "title")
ANSWER_KEYS = ("a", "answer", "text", "content", "body", "value")

def _detect_cols(header: List[str]) -> Tuple[Optional[str], Optional[str]]:
    low = [h.strip().lower() for h in header]
    q_col = next((h for h in low if h in QUESTION_KEYS), None)
    a_col = next((h for h in low if h in ANSWER_KEYS), None)
    return q_col, a_col

def _load_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return rows
            # 列検出
            q_col, a_col = _detect_cols(reader.fieldnames)
            if q_col is None or a_col is None:
                # 列名が想定外でも、先頭2列を q,a として試す
                names = [h.strip() for h in reader.fieldnames]
                if len(names) >= 2:
                    q_col, a_col = names[0], names[1]
                else:
                    return rows
            for i, rec in enumerate(reader, start=2):  # headerを1行目とみなす
                q = (rec.get(q_col) or "").strip()
                a = (rec.get(a_col) or "").strip()
                if not q and not a:
                    continue
                src = f"{path.name}:L{i}"
                rows.append({"q": q, "a": a, "source": src})
    except FileNotFoundError:
        pass
    return rows

def build_index() -> int:
    global INDEX
    INDEX = []
    for p in sorted(Path(".").glob("answers*.csv")):
        INDEX.extend(_load_csv(p))
    return len(INDEX)

def _score(query: str, row_q: str, row_a: str) -> float:
    q = query.strip()
    if not q:
        return 0.0
    # 部分一致を強く評価
    low_q = q.lower()
    rq = row_q.lower()
    ra = row_a.lower()
    if low_q in rq or low_q in ra:
        return 1.0
    # それ以外は類似度
    sim_q = difflib.SequenceMatcher(None, q, row_q).ratio()
    sim_a = difflib.SequenceMatcher(None, q, row_a).ratio()
    return max(sim_q, sim_a)

def search(query: str, top_k: int, min_score: float) -> List[Dict[str, str]]:
    scored: List[Tuple[float, Dict[str, str]]] = []
    for row in INDEX:
        s = _score(query, row["q"], row["a"])
        if s >= min_score:
            scored.append((s, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[: max(1, top_k)]]

# =========
# ルート
# =========
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": app.version,
        "build_time": os.environ.get("BUILD_TIME", "unknown"),
        "uptime_sec": float(os.environ.get("UPTIME_SEC", "0")) or 0.0,
    }

@app.get("/")
def root():
    return {"ok": True, "service": "app"}

@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask_get(
    q: str,
    top_k: int = 3,
    min_score: float = 0.2,
    lang: Optional[str] = "ja",
):
    hits = search(q, top_k, min_score)
    if not hits:
        return AskResponse(q=q, lang=lang or "ja", answer="[ja] 該当が見つかりませんでした。", sources=[])
    best = hits[0]
    # 1件の代表回答 + 参照元一覧
    return AskResponse(
        q=q,
        lang=lang or "ja",
        answer=f"[ja] {best['a']}",
        sources=[h["source"] for h in hits],
    )

@app.post("/feedback", summary="Feedback")
def feedback_feedback_post(payload: FeedbackIn = Body(...)):
    Path("./data/feedback").mkdir(parents=True, exist_ok=True)
    out = Path("./data/feedback") / f"{datetime.now():%Y%m%d}.jsonl"
    rec = payload.dict()
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(out)}

@app.post("/admin/reindex", summary="Rebuild in-memory index")
def admin_reindex():
    n = build_index()
    return {"ok": True, "loaded_rows": n}

# 起動時に読み込み
@app.on_event("startup")
def _on_startup():
    build_index()
