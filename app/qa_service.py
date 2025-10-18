# qa_service.py
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Query, Body
from pydantic import BaseModel, Field

APP_VERSION = "dev"

# データ配置
DATA_DIR = Path("./data")
DOCS_DIR = DATA_DIR / "docs"       # 実データの .txt をここへ置く
FEEDBACK_DIR = DATA_DIR / "feedback"
INDEX_PATH = DATA_DIR / "index.json"

DOCS_DIR.mkdir(parents=True, exist_ok=True)
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="gov-data-poc",
    version=APP_VERSION,
)

# ---------------------------
# モデル
# ---------------------------
class AskRequest(BaseModel):
    q: str = Field(..., title="Query", description="質問文")
    top_k: int = Field(3, ge=1, le=50, title="TopK")
    min_score: float = Field(0.0, ge=0.0, title="MinScore")
    lang: str = Field("ja", title="Lang")

class SourceItem(BaseModel):
    id: str
    score: float
    snippet: str

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[SourceItem] = []

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = []
    lang: str = "ja"

# ---------------------------
# 検索用の極シンプルなインデックス
# ---------------------------
_index: List[Dict[str, Any]] = []

def _normalize(text: str) -> str:
    # ひらがな/カタカナ変換などは未実装。まずは大小無視と空白統一のみ。
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    return t.lower()

def _tokenize(q: str) -> List[str]:
    # 空白で素直に分割（日本語でもそのまま全文一致で数を数える）
    # あまりに短い単語は除去
    parts = re.findall(r"\S+", q)
    return [p for p in parts if len(p) >= 1]

def build_index() -> Dict[str, Any]:
    """./data/docs の .txt を読み、index.json へ保存してからロード"""
    docs = []
    for p in sorted(DOCS_DIR.rglob("*.txt")):
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        docs.append({
            "id": str(p),
            "text": raw,
            "norm": _normalize(raw),
        })
    INDEX_PATH.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    load_index()
    return {"ok": True, "files": len(docs)}

def load_index() -> None:
    global _index
    if INDEX_PATH.exists():
        _index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    else:
        _index = []

def _score(q: str, norm_text: str) -> float:
    # クエリ単語が何回出るかの合計
    score = 0
    for term in set(_tokenize(q.lower())):
        if not term:
            continue
        score += norm_text.count(term)
    return float(score)

def search_docs(q: str, top_k: int, min_score: float) -> List[SourceItem]:
    results: List[SourceItem] = []
    for d in _index:
        s = _score(q, d["norm"])
        if s >= min_score:
            results.append(SourceItem(
                id=d["id"],
                score=s,
                snippet=d["text"][:160].replace("\n", " "),
            ))
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:top_k]

# ---------------------------
# エンドポイント
# ---------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": APP_VERSION,
        "build_time": "unknown",
        "uptime_sec": 0,
    }

@app.get("/", summary="Root")
def root_get():
    return {}

@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask_get(
    q: str = Query(..., description="質問文"),
    lang: str = Query("ja", description="言語"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.0, ge=0.0),
):
    sources = search_docs(q, top_k=top_k, min_score=min_score)
    answer = _compose_answer(q, sources, lang)
    return AskResponse(q=q, lang=lang, answer=answer, sources=sources)

@app.post("/ask", response_model=AskResponse, summary="Ask (POST)")
def ask_post(payload: AskRequest = Body(...)):
    sources = search_docs(payload.q, top_k=payload.top_k, min_score=payload.min_score)
    answer = _compose_answer(payload.q, sources, payload.lang)
    return AskResponse(q=payload.q, lang=payload.lang, answer=answer, sources=sources)

def _compose_answer(q: str, sources: List[SourceItem], lang: str) -> str:
    if not sources:
        return "該当する情報が見つかりませんでした。キーワードを変えて再検索してください。"
    # とりあえず上位のスニペットを繋いで返す（後でLLM要約に差し替え予定）
    joined = " / ".join(s.snippet for s in sources[:2])
    return f"[試験的な回答] {joined}"

@app.post("/feedback", summary="Feedback")
def feedback_post(body: FeedbackIn):
    today = datetime.utcnow().strftime("%Y%m%d")
    path = FEEDBACK_DIR / f"{today}.jsonl"
    rec = body.model_dump()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(path)}

@app.post("/admin/reindex", summary="Rebuild simple index")
def admin_reindex():
    return build_index()

# ---------------------------
# 起動時に既存インデックス読み込み
# ---------------------------
@app.on_event("startup")
def _on_startup():
    load_index()
