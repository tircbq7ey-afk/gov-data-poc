# app/qa_service.py
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

APP_PORT = int(os.getenv("APP_PORT", "8010"))
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token")

# 必要フォルダ作成
for p in (WEB_ROOT, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

started_at = datetime.now(timezone.utc)

app = FastAPI(title="gov-data-poc", version="dev")

# CORS（必要なければ削ってOK）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def _require_api_key(x_api_key: Optional[str]):
    if x_api_key is None or x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid api key")

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "gov-data-poc",
        "version": app.version,
        "build_time": "unknown",
        "uptime_sec": (datetime.now(timezone.utc) - started_at).total_seconds(),
    }

@app.get("/openapi.json")
def openapi_redirect():
    # 一部のツール確認用（Nginx越しでも取れるように）
    return app.openapi()

@app.get("/ask")
def ask(q: str, lang: str = "ja"):
    # ダミー回答（検索やRAGは未実装のまま）
    return {
        "q": q,
        "lang": lang,
        "answer": f"[{lang}] echo: {q}",
        "sources": [],
    }

@app.post("/feedback")
def feedback(
    payload: dict,
    x_api_key: Optional[str] = Header(None)
):
    _require_api_key(x_api_key)

    # 期待キー：q, answer, sources(list), label, lang
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = FEEDBACK_DIR / f"{today}.jsonl"
    payload = dict(payload)
    payload["ts"] = datetime.now(timezone.utc).isoformat()

    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return {"ok": True, "path": str(out.relative_to(DATA_DIR.parent)) if str(DATA_DIR.parent) in str(out) else str(out)}

@app.post("/admin/reindex")
def admin_reindex(
    force: bool = False,
    x_api_key: Optional[str] = Header(None)
):
    _require_api_key(x_api_key)

    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    flag = FLAGS_DIR / "reindexed_at.txt"
    flag.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    return {"ok": True, "forced": force, "flag_path": str(flag)}
