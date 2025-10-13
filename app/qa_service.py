from __future__ import annotations
from fastapi import FastAPI, Body, Header
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Tuple
from pathlib import Path
import re
import json
import time

app = FastAPI(title="gov-data-poc", version="dev")

# ===== 検索用・超軽量インデックス（外部ライブラリなし） =====
_DOCS: List[Dict] = []
_INV: Dict[str, Dict[int, int]] = {}  # token -> {doc_id: tf}
_IDF: Dict[str, float] = {}
_TOKEN = re.compile(r"[A-Za-z0-9一-龠ぁ-んァ-ンー]+")

def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN.findall(text)]

def _build_index(docs: List[Dict[str, str]]) -> None:
    global _DOCS, _INV, _IDF
    _DOCS = []
    _INV = {}
    for i, d in enumerate(docs):
        text = f"{d.get('q','')} {d.get('a','')}"
        toks = _tokenize(text)
        _DOCS.append({"id": i, "q": d.get("q",""), "a": d.get("a",""), "path": d.get("path","")})
        seen = {}
        for tok in toks:
            seen[tok] = seen.get(tok, 0) + 1
        for tok, tf in seen.items():
            _INV.setdefault(tok, {})[i] = tf

    # IDF（ゆるい計算）
    N = max(1, len(_DOCS))
    _IDF = {}
    for tok, postings in _INV.items():
        df = len(postings)
        _IDF[tok] = max(0.0, ( (N - df + 0.5) / (df + 0.5) ))

def _score_query(q: str) -> List[Tuple[int, float]]:
    if not _DOCS:
        return []
    q_toks = _tokenize(q)
    cand: Dict[int, float] = {}
    for tok in q_toks:
        postings = _INV.get(tok)
        if not postings:
            continue
        idf = _IDF.get(tok, 0.0)
        for doc_id, tf in postings.items():
            cand[doc_id] = cand.get(doc_id, 0.0) + idf * (1.0 + tf)
    # スコア降順
    return sorted(cand.items(), key=lambda x: x[1], reverse=True)

def _lazy_bootstrap_index():
    # まだインデックスが無ければ ./data / ルートCSVから作る
    if _DOCS:
        return
    sources: List[Dict[str, str]] = []

    # 1) ./data 以下の .csv / .md / .txt
    data_dir = Path("./data")
    if data_dir.exists():
        for p in data_dir.rglob("*"):
            if p.suffix.lower() == ".csv":
                try:
                    import csv
                    with p.open("r", encoding="utf-8", newline="") as f:
                        rdr = csv.DictReader(f)
                        for row in rdr:
                            q = row.get("q") or row.get("question") or ""
                            a = row.get("a") or row.get("answer") or ""
                            if q or a:
                                sources.append({"q": q, "a": a, "path": str(p)})
                except Exception:
                    pass
            elif p.suffix.lower() in {".md", ".txt"}:
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    # 1行目を「q」、残りを「a」扱い（サンプル）
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    if lines:
                        q = lines[0]
                        a = "\n".join(lines[1:]) if len(lines) > 1 else lines[0]
                        sources.append({"q": q, "a": a, "path": str(p)})
                except Exception:
                    pass

    # 2) リポジトリ直下の CSV（answers.csv 等）
    for p in Path(".").glob("answers*.csv"):
        try:
            import csv
            with p.open("r", encoding="utf-8", newline="") as f:
                rdr = csv.DictReader(f)
                for row in rdr:
                    q = row.get("q") or row.get("question") or ""
                    a = row.get("a") or row.get("answer") or ""
                    if q or a:
                        sources.append({"q": q, "a": a, "path": str(p)})
        except Exception:
            pass

    if not sources:
        # ソースがなければダミー1件
        sources = [{"q": "ダミーの質問", "a": "ダミーの回答。/admin/reindex で実データを読み込めます。", "path": "memory"}]

    _build_index(sources)

def _search(q: str, top_k: int, min_score: float):
    _lazy_bootstrap_index()
    started = time.time()
    ranked = _score_query(q)
    hits = []
    for doc_id, score in ranked[: max(1, top_k * 3)]:
        if score < min_score:
            continue
        d = _DOCS[doc_id]
        snippet = (d["a"] or d["q"])[:120]
        hits.append({
            "loc": d["path"],
            "score": round(float(score), 3),
            "snippet": snippet
        })
    took = int((time.time() - started) * 1000)
    # 回答（とりあえず上位1件の回答を返す）
    answer = _DOCS[ranked[0][0]]["a"] if ranked else ""
    return answer, hits, took

# ====== I/O モデル ======
class AskResponse(BaseModel):
    q: str
    lang: str = "ja"
    answer: str
    sources: List[Dict[str, str]] = Field(default_factory=list)

class AskIn(BaseModel):
    q: str
    top_k: int = 5
    min_score: float = 0.0

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    lang: Optional[str] = None

# ====== ヘルス ======
@app.get("/health")
def health():
    return {"ok": True, "version": app.version, "build_time": "unknown", "uptime_sec": 0}

# ====== Ask（GET） ======
@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask_get(
    q: str,
    lang: Optional[str] = "ja",
    top_k: int = 5,
    min_score: float = 0.0,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key")
):
    answer, hits, _ = _search(q, top_k, min_score)
    return AskResponse(q=q, lang=lang or "ja", answer=answer, sources=hits)

# ====== Ask（POST） ======
@app.post("/ask", response_model=AskResponse, summary="Ask (POST)")
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key")
):
    answer, hits, _ = _search(body.q, body.top_k, body.min_score)
    return AskResponse(q=body.q, lang="ja", answer=answer, sources=hits)

# ====== Feedback ======
@app.post("/feedback", summary="Feedback")
def feedback(
    fb: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key")
):
    out_dir = Path("./data/feedback")
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = time.strftime("%Y%m%d") + ".jsonl"
    path = out_dir / fname
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fb.dict(), ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(path)}

# ====== Reindex（実データ読込） ======
@app.post("/admin/reindex", summary="Reindex data directory")
def admin_reindex(
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key")
):
    started = time.time()
    # ./data と answers*.csv を再走査
    sources: List[Dict[str, str]] = []
    data_dir = Path("./data")
    if data_dir.exists():
        for p in data_dir.rglob("*"):
            if p.suffix.lower() == ".csv":
                try:
                    import csv
                    with p.open("r", encoding="utf-8", newline="") as f:
                        rdr = csv.DictReader(f)
                        for row in rdr:
                            q = row.get("q") or row.get("question") or ""
                            a = row.get("a") or row.get("answer") or ""
                            if q or a:
                                sources.append({"q": q, "a": a, "path": str(p)})
                except Exception:
                    pass
            elif p.suffix.lower() in {".md", ".txt"}:
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    if lines:
                        q = lines[0]
                        a = "\n".join(lines[1:]) if len(lines) > 1 else lines[0]
                        sources.append({"q": q, "a": a, "path": str(p)})
                except Exception:
                    pass
    for p in Path(".").glob("answers*.csv"):
        try:
            import csv
            with p.open("r", encoding="utf-8", newline="") as f:
                rdr = csv.DictReader(f)
                for row in rdr:
                    q = row.get("q") or row.get("question") or ""
                    a = row.get("a") or row.get("answer") or ""
                    if q or a:
                        sources.append({"q": q, "a": a, "path": str(p)})
        except Exception:
            pass

    if not sources:
        sources = [{"q": "ダミーの質問", "a": "ダミーの回答", "path": "memory"}]

    _build_index(sources)
    took = int((time.time() - started) * 1000)
    return {"ok": True, "docs": len(_DOCS), "took_ms": took}
