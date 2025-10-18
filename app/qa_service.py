from __future__ import annotations

from fastapi import FastAPI, Body, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import json
import re

APP_TITLE = "gov-data-poc"
DATA_DIR = Path("./data")
DOCS_DIR = DATA_DIR / "docs"         # ← 実データはここに置く（.txt/.md/.json など）
INDEX_PATH = DATA_DIR / "index.json" # ← 簡易インデックス（再作成可能）
FEEDBACK_DIR = DATA_DIR / "feedback"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=APP_TITLE,
    version="dev"
)

# ----------------------
# Pydantic モデル
# ----------------------
class AskIn(BaseModel):
    q: str = Field(..., description="ユーザーの質問")
    top_k: int = Field(3, ge=1, le=20)
    min_score: float = Field(0.2, ge=0.0, le=1.0)
    lang: str = Field("ja", description="応答言語")

class Source(BaseModel):
    id: str
    path: str
    score: float
    snippet: str

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[Source]

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = []
    lang: str = "ja"

class ReindexResult(BaseModel):
    ok: bool
    docs: int
    index_path: str

# ----------------------
# ユーティリティ
# ----------------------
def _load_index() -> Dict[str, Any]:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {"built_at": None, "docs": []}

def _save_index(idx: Dict[str, Any]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")

def _tokenize(text: str) -> List[str]:
    # 超簡易：英数字と日本語をザックリ単語化
    return [t for t in re.findall(r"[A-Za-z0-9_]+|[\u3040-\u30ff\u4e00-\u9fff]+", text)]

def _score(q_tokens: List[str], doc_text: str) -> float:
    # 極めて簡易なスコアリング（クエリ語が多く含まれるほど高スコア）
    tokens = _tokenize(doc_text)
    if not tokens:
        return 0.0
    hit = sum(tokens.count(t) for t in q_tokens)
    return min(1.0, hit / (len(q_tokens) * 5.0 + 1e-6))

def _build_index_from_docs() -> ReindexResult:
    docs: List[Dict[str, Any]] = []
    doc_id = 0
    for p in DOCS_DIR.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in [".txt", ".md", ".json"]:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            try:
                text = p.read_text(encoding="cp932")
            except Exception:
                continue
        docs.append({
            "id": f"doc_{doc_id}",
            "path": str(p),
            "text": text
        })
        doc_id += 1
    idx = {"built_at": datetime.utcnow().isoformat(), "docs": docs}
    _save_index(idx)
    return ReindexResult(ok=True, docs=len(docs), index_path=str(INDEX_PATH))

def _search_answer(q: str, top_k: int, min_score: float) -> List[Source]:
    idx = _load_index()
    candidates: List[Source] = []
    q_tokens = _tokenize(q)
    for d in idx.get("docs", []):
        s = _score(q_tokens, d["text"])
        if s >= min_score:
            # スニペット（先頭 120 文字）
            snippet = d["text"].strip().replace("\n", " ")
            snippet = snippet[:120]
            candidates.append(Source(id=d["id"], path=d["path"], score=round(s, 3), snippet=snippet))
    candidates.sort(key=lambda x: x.score, reverse=True)
    return candidates[:top_k]

def _draft_answer(q: str, sources: List[Source], lang: str) -> str:
    # まずは素朴に：ヒットがあれば要約風、なければ“情報なし”
    if not sources:
        return "関連する情報が見つかりませんでした。検索条件（top_k / min_score）を調整して再度お試しください。"
    # very naive: 最上位のスニペットを返す
    best = sources[0]
    return f"候補資料からの抜粋: {best.snippet}（出典: {Path(best.path).name}）"

# ----------------------
# エンドポイント
# ----------------------
@app.get("/health")
def health():
    return {"ok": True, "version": "dev", "build_time": "unknown"}

# GET /ask（既存の互換）
@app.get("/ask", response_model=AskResponse)
def ask_get(q: str, top_k: int = 3, min_score: float = 0.2, lang: str = "ja"):
    sources = _search_answer(q, top_k, min_score)
    answer = _draft_answer(q, sources, lang)
    return AskResponse(q=q, lang=lang, answer=answer, sources=sources)

# ★ 追加：POST /ask（JSON ボディ対応）
@app.post("/ask", response_model=AskResponse)
def ask_post(payload: AskIn = Body(...)):
    sources = _search_answer(payload.q, payload.top_k, payload.min_score)
    answer = _draft_answer(payload.q, sources, payload.lang)
    return AskResponse(q=payload.q, lang=payload.lang, answer=answer, sources=sources)

# 既存：POST /feedback（そのまま活かす）
@app.post("/feedback")
def feedback(fb: FeedbackIn):
    day = datetime.now().strftime("%Y%m%d")
    out = FEEDBACK_DIR / f"{day}.jsonl"
    rec = fb.dict()
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(out)}

# ★ 追加：POST /admin/reindex（実データでの検索“準備”）
@app.post("/admin/reindex", response_model=ReindexResult)
def admin_reindex():
    return _build_index_from_docs()
