from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Body, Query
from fastapi.responses import JSONResponse

APP_PORT = int(Path.env.get("APP_PORT", "8010")) if hasattr(Path, "env") else 8010  # safe fallback
WEB_ROOT = Path("/usr/share/nginx/html")  # 静的配信はNginxで行う
DATA_DIR = Path("/app/data").resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"

# 必要なディレクトリを起動時に作る
for p in (DATA_DIR, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="gov-data-poc", version="dev")


@app.get("/health")
def health():
    return {"ok": True, "version": "dev", "build_time": "unknown", "uptime_sec": None}


@app.get("/ask")
def ask(q: str = Query(..., description="question"), lang: str = "ja"):
    # デモ：そのまま返す（ここに検索やRAGを後で実装）
    return {"q": q, "lang": lang, "answer": "[ja] これはデモ回答です。", "sources": []}


@app.post("/feedback")
def feedback(
    payload: dict = Body(..., description="{'q','answer','sources','label','lang'} を含むJSON")
):
    # 日毎に jsonl 追記
    ts = datetime.now(timezone.utc).isoformat()
    payload = dict(payload)
    payload["ts"] = ts

    out = FEEDBACK_DIR / f"{datetime.now().strftime('%Y%m%d')}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return {"ok": True, "path": f"./data/feedback/{out.name}"}


@app.post("/admin/reindex")
def admin_reindex(force: bool = Body(False)):
    """
    疑似リインデックス。
    実際の索引処理は後段で実装予定だとして、ここではフラグを書くだけ。
    """
    flag = FLAGS_DIR / "reindexed_at.txt"
    flag.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    return {"ok": True, "forced": bool(force), "flag": str(flag)}
