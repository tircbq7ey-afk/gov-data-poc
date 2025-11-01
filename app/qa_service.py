from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

APP_START = datetime.now(timezone.utc)

DATA_DIR = Path("/app/data")
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"
for p in (DATA_DIR, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

class AskResponse(BaseModel):
    q: str
    lang: str = "ja"
    answer: str
    sources: List[str] = []

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    label: str = "good"
    lang: str = "ja"

class FeedbackOut(BaseModel):
    ok: bool = True
    path: str

class HealthOut(BaseModel):
    ok: bool
    service: str = "gov-data-poc"
    version: str = "dev"
    build_time: str = "unknown"
    uptime_sec: float

app = FastAPI(title="gov-data-poc")

@app.get("/health", response_model=HealthOut)
def health():
    return HealthOut(
        ok=True,
        uptime_sec=(datetime.now(timezone.utc) - APP_START).total_seconds(),
    )

@app.get("/ask")
def ask(q: str, lang: str = "ja"):
    # デモ用の固定応答（必要に応じてRAG等に差し替え）
    ans = "オンラインで申請できます。"
    return AskResponse(q=q, lang=lang, answer=ans, sources=[])

@app.post("/feedback", response_model=FeedbackOut)
def feedback(fb: FeedbackIn):
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    jpath = FEEDBACK_DIR / f"{today}.jsonl"
    rec = {
        "q": fb.q,
        "answer": fb.answer,
        "sources": fb.sources,
        "label": fb.label,
        "lang": fb.lang,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with jpath.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # 取り回し用：最新取り込みフラグを消す（再インデックス待ち）
    flag = FLAGS_DIR / "reindexed_at.txt"
    if flag.exists():
        flag.unlink(missing_ok=True)
    return FeedbackOut(ok=True, path=str(jpath).replace("/app", "."))

class ReindexIn(BaseModel):
    force: Optional[bool] = False

@app.post("/admin/reindex")
def admin_reindex(body: ReindexIn):
    """
    ここで実際のインデックス更新処理を行う想定。
    デモとして flags/reindexed_at.txt を更新し、200を返す。
    """
    (FLAGS_DIR).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (FLAGS_DIR / "reindexed_at.txt").write_text(stamp + "\n", encoding="utf-8")
    return {"ok": True, "reindexed_at": stamp, "force": bool(body.force)}
