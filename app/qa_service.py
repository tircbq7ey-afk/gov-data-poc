# /app/qa_service.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

APP_PORT = int(os.getenv("APP_PORT", "8010"))
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"

for p in (WEB_ROOT, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

started_at = datetime.now(timezone.utc)

app = FastAPI(title="gov-data-poc", version="dev")

# --- 静的ファイル (index.html を / と /index.html で配信) ---
if (WEB_ROOT / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(WEB_ROOT), html=True), name="static")

    @app.get("/index.html")
    async def _index_alias():
        return FileResponse(WEB_ROOT / "index.html")
# -----------------------------------------------------------

@app.get("/health")
def health(x_api_key: Optional[str] = Header(default=None)):
    uptime = (datetime.now(timezone.utc) - started_at).total_seconds()
    return {"ok": True, "version": "dev", "build_time": "unknown", "uptime_sec": round(uptime, 2)}

@app.get("/ask")
def ask(
    q: str = Query(..., description="question"),
    lang: str = Query("ja"),
    top_k: int = Query(3, ge=1, le=10),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
    x_api_key: Optional[str] = Header(default=None),
):
    # ここは PoC。実際の検索/推論の代わりにダミー応答を返す
    answer = "オンラインで申請できます。"
    return {"q": q, "lang": lang, "answer": answer, "sources": []}

@app.post("/feedback")
def feedback(
    payload: dict,
    x_api_key: Optional[str] = Header(default=None),
):
    # 期待スキーマ: {"q": "...", "answer": "...", "sources": ["..."], "lang": "ja", "label": "good"}
    q = payload.get("q")
    answer = payload.get("answer")
    sources = payload.get("sources", [])
    lang = payload.get("lang", "ja")
    label = payload.get("label", "good")
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if not q or not answer:
        return JSONResponse({"detail": "q and answer are required"}, status_code=422)

    line = {"q": q, "answer": answer, "sources": sources, "lang": lang, "label": label, "ts": ts}
    out = FEEDBACK_DIR / (datetime.now(timezone.utc).strftime("%Y%m%d") + ".jsonl")
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

    return {"ok": True, "path": str(out)}

@app.post("/admin/reindex")
def admin_reindex(force: bool = True, x_api_key: Optional[str] = Header(default=None)):
    # Reindex フラグファイルを作るだけ（PoC）
    flag = FLAGS_DIR / (datetime.now(timezone.utc).strftime("reindex.%Y%m%d-%H%M%S.flag"))
    flag.write_text("reindex\n", encoding="utf-8")
    return {"ok": True, "flag": str(flag)}
