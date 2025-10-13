from __future__ import annotations

from fastapi import FastAPI, Header
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import csv
import math
import re
import json

app = FastAPI(title="gov-data-poc", version="0.1.0")

# ------------------------------
# モデル
# ------------------------------
class AskResponseHit(BaseModel):
    score: float
    q: str
    a: str
    source: Optional[str] = None
    lang: Optional[str] = None

class AskResponse(BaseModel):
    q: str
    lang: str = "ja"
    answer: str
    sources: List[AskResponseHit] = Field(default_factory=list)

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

class FeedbackOut(BaseModel):
    ok: bool
    path: str

# ------------------------------
# 文字 bi-gram とコサイン類似度（日本語でも動く軽量版）
# ------------------------------
_nonword = re.compile(r"\s+")

def bigrams(text: str) -> Dict[str, int]:
    # スペース区切りが無い言語でも効くように、文字bi-gramにする
    s = _nonword.sub("", text or "")
    grams = [s[i:i+2] for i in range(max(0, len(s)-1))]
    bag: Dict[str, int] = {}
    for g in grams:
        bag[g] = bag.get(g, 0) + 1
    return bag

def cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
    if not a or not b:
        return 0.0
    dot = 0
    for k, v in a.items():
        if k in b:
            dot += v * b[k]
    na = math.sqrt(sum(v*v for v in a.values()))
    nb = math.sqrt(sum(v*v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

# ------------------------------
# データ読み込み（./answers.csv）
# ------------------------------
class Doc(BaseModel):
    q: str
    a: str
    lang: str = "ja"
    source: Optional[str] = None
    _vec: Dict[str, int] = {}

DATA: List[Doc] = []

def load_data() -> None:
    global DATA
    DATA = []
    csv_path = Path("./answers.csv")
    if not csv_path.exists():
        # 予備：空でも起動できるようにダミーデータ
        DATA = [
            Doc(q="申請書の提出方法", a="窓口またはオンラインで提出できます。詳細は担当課のページをご確認ください。", lang="ja", source="dummy"),
        ]
    else:
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                q = (row.get("q") or row.get("question") or "").strip()
                a = (row.get("a") or row.get("answer") or "").strip()
                lang = (row.get("lang") or "ja").strip() or "ja"
                source = (row.get("source") or row.get("src") or "").strip() or None
                if q and a:
                    DATA.append(Doc(q=q, a=a, lang=lang, source=source))

    # ベクトル前計算
    for d in DATA:
        d._vec = bigrams(d.q)

load_data()

# ------------------------------
# ヘルス
# ------------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": "dev",
        "build_time": "unknown",
        "uptime_sec": 0,  # 簡易
    }

# ------------------------------
# 検索（GET /ask）
# ------------------------------
@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask(
    q: str,
    top_k: int = 3,
    min_score: float = 0.2,
    lang: str = "ja",
    x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key"),
):
    # 入力の前計算
    q_vec = bigrams(q)

    # lang で絞り込み（必要に応じて）
    cand = [d for d in DATA if (not lang or d.lang == lang)]

    # スコアリング
    scored: List[AskResponseHit] = []
    for d in cand:
        s = cosine(q_vec, d._vec)
        if s >= min_score:
            scored.append(AskResponseHit(score=round(s, 4), q=d.q, a=d.a, source=d.source, lang=d.lang))

    scored.sort(key=lambda x: x.score, reverse=True)
    top = scored[: max(1, top_k)] if scored else []

    # 応答のまとめ（ヒット無しならテンプレ）
    if top:
        answer_text = top[0].a
    else:
        answer_text = "該当する情報が見つかりませんでした。キーワードを変えて再検索してください。"

    return AskResponse(q=q, lang=lang, answer=answer_text, sources=top)

# ------------------------------
# フィードバック（POST /feedback）
# ------------------------------
@app.post("/feedback", response_model=FeedbackOut, summary="Feedback")
def feedback(
    payload: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key"),
):
    # JSON Lines で日付ファイルに追記
    outdir = Path("./data/feedback")
    outdir.mkdir(parents=True, exist_ok=True)
    outpath = outdir / f"{datetime.utcnow():%Y%m%d}.jsonl"

    with outpath.open("a", encoding="utf-8") as w:
        w.write(json.dumps(payload.dict(), ensure_ascii=False) + "\n")

    return FeedbackOut(ok=True, path=str(outpath))
