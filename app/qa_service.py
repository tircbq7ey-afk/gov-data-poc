from __future__ import annotations

import csv
import glob
import os
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel
from difflib import SequenceMatcher

APP_VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
BUILD_SHA = os.getenv("BUILD_SHA", "unknown")

app = FastAPI(title="gov-data-poc", version="0.1.0")


# ==== Pydantic models =========================================================
class AskRequest(BaseModel):
    q: str
    top_k: int = 5
    min_score: float = 0.0  # 0.0 - 1.0 目安


class AskResponse(BaseModel):
    hits: List[str]
    took_ms: int


# ==== very simple in-memory corpus ============================================
_CORPUS: List[str] = []


def _pick_text_columns(header: List[str]) -> List[int]:
    """
    CSV の見出しから文章っぽい列候補を雑に推定します。
    優先: answer, text, content, a, body
    見出しが無ければ全列を結合
    """
    if not header:
        return []

    keys = [h.strip().lower() for h in header]
    priority = ["answer", "text", "content", "body", "a", "説明", "回答"]
    for key in priority:
        if key in keys:
            return [keys.index(key)]

    # それっぽい名前が無ければ、文字列列っぽいものを全部
    return list(range(len(keys)))


def _load_corpus() -> List[str]:
    base = Path(".")
    patterns = [
        base / "*.csv",
        base / "data" / "*.csv",
        base / "static" / "*.csv",
    ]
    paths: List[Path] = []
    for p in patterns:
        paths.extend(Path(".").glob(str(p)))

    corpus: List[str] = []

    for path in paths:
        try:
            with path.open("r", encoding="utf-8", newline="") as f:
                sniffer = csv.Sniffer()
                sample = f.read(2048)
                f.seek(0)
                has_header = False
                try:
                    has_header = sniffer.has_header(sample)
                except Exception:
                    pass

                reader = csv.reader(f)
                header: List[str] = []
                if has_header:
                    header = next(reader, [])
                cols = _pick_text_columns(header)

                for row in reader:
                    if not row:
                        continue
                    if cols:
                        text = " ".join(row[i] for i in cols if i < len(row))
                    else:
                        text = " ".join(row)
                    text = text.strip()
                    if text:
                        corpus.append(text)
        except FileNotFoundError:
            continue
        except Exception:
            # CSV 以外は読み飛ばす（雑でOK）
            continue

    # 何も見つからなければ、最低限のダミーデータを入れる
    if not corpus:
        corpus = [
            "申請書はオンラインで提出できます。",
            "窓口の受付時間は平日 9:00-17:00 です。",
            "必要書類の原本をご持参ください。",
            "よくある質問と回答を掲載しています。",
        ]
    return corpus


@app.on_event("startup")
def _startup() -> None:
    global _CORPUS
    _CORPUS = _load_corpus()


# ==== endpoints ===============================================================
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": APP_VERSION,
        "build_time": BUILD_TIME,
        "build_sha": BUILD_SHA,
        "uptime_sec": 0,  # 簡略化
        "docs": 2,
    }


def _score(a: str, b: str) -> float:
    # 本当に簡易なスコア（0.0〜1.0）
    return SequenceMatcher(None, a, b).ratio()


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """
    超シンプルな全文“もどき”検索:
      - difflib の類似度で並べ替え
      - min_score 以上から top_k 件返す
    """
    t0 = time.perf_counter()

    scored = [(_score(req.q, doc), doc) for doc in _CORPUS]
    scored.sort(key=lambda x: x[0], reverse=True)

    hits = [doc for s, doc in scored if s >= req.min_score][: max(1, req.top_k)]

    took_ms = int((time.perf_counter() - t0) * 1000)
    return AskResponse(hits=hits, took_ms=took_ms)
