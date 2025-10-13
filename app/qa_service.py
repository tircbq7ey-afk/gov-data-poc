from __future__ import annotations

from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import csv
import json
import math
import re
import unicodedata

app = FastAPI(title="gov-data-poc", version="dev")

DATA_DIR = Path("./data")
FEEDBACK_DIR = DATA_DIR / "feedback"
# 探索候補CSV（存在する方を使う）
CANDIDATE_CSVS = [
    DATA_DIR / "answers.csv",
    DATA_DIR / "answers_A.csv",
]

# -------- Normalization / Tokenization (Japanese-friendly) --------
_jp_re = re.compile(r"[ぁ-んァ-ヶｱ-ﾝﾞﾟ一-龥々ー]+")  # JP連続部分
_ascii_re = re.compile(r"[A-Za-z0-9_]+")

def normalize_text(s: str) -> str:
    # 全角→半角などの正規化
    s = unicodedata.normalize("NFKC", s)
    return s.lower().strip()

def char_bigrams(seq: str) -> List[str]:
    # 文字単位のバイグラム（日本語連続部分に用いる）
    if len(seq) <= 1:
        return [seq] if seq else []
    return [seq[i:i+2] for i in range(len(seq)-1)]

def tokenize(text: str) -> List[str]:
    text = normalize_text(text)
    tokens: List[str] = []
    i = 0
    while i < len(text):
        m_jp = _jp_re.match(text, i)
        if m_jp:
            tokens.extend(char_bigrams(m_jp.group()))
            i = m_jp.end()
            continue
        m_en = _ascii_re.match(text, i)
        if m_en:
            tokens.append(m_en.group())
            i = m_en.end()
            continue
        # スキップ（記号・空白など）
        i += 1
    return tokens or ([] if not text else [text])

# -------- Minimal BM25 (pure Python) --------
class BM25Index:
    def __init__(self, k1: float = 1.2, b: float = 0.75, delta: float = 1.0):
        self.k1 = k1
        self.b = b
        self.delta = delta
        self.docs: List[Dict[str, Any]] = []
        self.avgdl = 0.0
        self.df: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.tf: List[Dict[str, int]] = []
        self.doc_len: List[int] = []

    def fit(self, docs: List[Dict[str, Any]], field: str = "text") -> None:
        self.docs = docs
        self.tf = []
        self.doc_len = []
        self.df = {}
        # TF/DF 計算
        for d in docs:
            toks = tokenize(d[field])
            cnt: Dict[str, int] = {}
            for t in toks:
                cnt[t] = cnt.get(t, 0) + 1
            self.tf.append(cnt)
            self.doc_len.append(len(toks))
            for t in cnt.keys():
                self.df[t] = self.df.get(t, 0) + 1
        self.avgdl = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0
        N = max(1, len(docs))
        # BM25+ の idf（負になりにくいように +0.5 平滑化）
        for t, df in self.df.items():
            self.idf[t] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query: str, idx: int) -> float:
        if not self.docs:
            return 0.0
        q_toks = tokenize(query)
        tf = self.tf[idx]
        dl = self.doc_len[idx] or 1
        score = 0.0
        for t in q_toks:
            if t not in tf:
                continue
            f = tf[t]
            idf = self.idf.get(t, 0.0)
            denom = f + self.k1 * (1 - self.b + self.b * (dl / (self.avgdl or 1)))
            score += idf * ((f * (self.k1 + 1)) / denom + self.delta)
        return score

    def search(self, query: str, top_k: int = 5, min_score: float = 0.0) -> List[Dict[str, Any]]:
        scored = []
        for i, d in enumerate(self.docs):
            s = self.score(query, i)
            if s >= min_score:
                scored.append((s, i))
        scored.sort(reverse=True)
        out = []
        for s, i in scored[:top_k]:
            dd = self.docs[i].copy()
            dd["score"] = round(float(s), 4)
            out.append(dd)
        return out

# -------- Data loading --------
def find_data_csv() -> Optional[Path]:
    for p in CANDIDATE_CSVS:
        if p.exists():
            return p
    return None

def load_docs() -> List[Dict[str, Any]]:
    csv_path = find_data_csv()
    if not csv_path:
        return []
    docs: List[Dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # 列名推定（question/answer or q/a）
        cols = {k.lower(): k for k in reader.fieldnames or []}
        kq = cols.get("q") or cols.get("question") or next(iter(cols.values()), None)
        ka = cols.get("a") or cols.get("answer")
        for i, row in enumerate(reader):
            q = (row.get(kq or "", "") or "").strip()
            a = (row.get(ka or "", "") or "").strip()
            text = f"{q}\n{a}".strip() if a else q
            docs.append({
                "id": f"row_{i+1}",
                "q": q,
                "answer": a,
                "text": text
            })
    return docs

INDEX = BM25Index()
INDEX.fit(load_docs())

# -------- Schemas --------
class AskResponse(BaseModel):
    q: str
    lang: str = "ja"
    answer: str = ""
    sources: List[Dict[str, Any]] = []

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = []
    lang: Optional[str] = "ja"

class HealthOut(BaseModel):
    ok: bool
    version: str
    build_time: str
    uptime_sec: float

# -------- Endpoints --------
_start_time = datetime.now()

@app.get("/health", response_model=HealthOut, summary="Health")
def health():
    delta = datetime.now() - _start_time
    return HealthOut(ok=True, version="dev", build_time="unknown", uptime_sec=round(delta.total_seconds(), 2))

@app.get("/", summary="Root")
def root_get():
    return {"ok": True}

@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask_get(
    q: str,
    lang: str = "ja",
    top_k: int = 5,
    min_score: float = 0.0,
):
    hits = INDEX.search(q, top_k=top_k, min_score=min_score)
    # 一番上をanswer、全件をsourcesに
    best_answer = ""
    if hits:
        # answer列が空なら text（=Q&A連結）から返す
        best_answer = hits[0].get("answer") or hits[0].get("text", "")
    return AskResponse(q=q, lang=lang, answer=best_answer, sources=hits)

@app.post("/feedback", summary="Feedback")
def feedback(feedback: FeedbackIn = Body(..., embed=False)):
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FEEDBACK_DIR / (datetime.now().strftime("%Y%m%d") + ".jsonl")
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(feedback.dict(), ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(out_path.relative_to(Path.cwd()))}

@app.post("/admin/reindex", summary="Rebuild index")
def admin_reindex():
    docs = load_docs()
    INDEX.fit(docs)
    return {"ok": True, "docs": len(docs)}
