from __future__ import annotations

import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ===== 環境・パス =====
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

APP_PORT = int(os.getenv("APP_PORT", "8010"))
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"

# 必要ディレクトリは必ず作成
for p in (WEB_ROOT, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

API_TOKEN = os.getenv("API_TOKEN", "").strip()  # 空なら認証なし

# ===== FastAPI =====
app = FastAPI(title="gov-data-poc", version=VERSION)

# ---- 静的配信（index.html があれば / と /index.html を返す）----
if (WEB_ROOT / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT), html=True), name="static")

    @app.get("/", include_in_schema=False)
    async def root_html():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")

    @app.get("/index.html", include_in_schema=False)
    async def index_alias():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")
else:
    @app.get("/", include_in_schema=False)
    async def root_json():
        return {"ok": True, "service": "gov-data-poc", "version": VERSION}

# ---- 認証ヘルパ ----
def _require(x_api_key: Optional[str]) -> None:
    # API_TOKEN が設定されている時だけチェック
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ---- ヘルス ----
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round(time.time() - START_TS, 2),
    }

# ---- /ask ----
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(...),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# ---- /feedback ----
class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    out = FEEDBACK_DIR / f"{datetime.utcnow():%Y%m%d}.jsonl"
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": str(out)})

# ---- /admin/reindex（フラグ作成）----
@app.post("/admin/reindex")
def admin_reindex(
    force: bool = True,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    flag = FLAGS_DIR / f"reindex.{ts}.flag"
    try:
        flag.write_text("reindex\n", encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to write flag: {e}")
    return {"ok": True, "flag": str(flag)}
