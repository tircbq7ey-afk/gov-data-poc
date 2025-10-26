from __future__ import annotations
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# === 設定 ===
APP_PORT = int(os.getenv("APP_PORT", "8010"))
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"
API_TOKEN = os.getenv("API_TOKEN", "").strip()

# ディレクトリは起動時に必ず作る
for p in (WEB_ROOT, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = datetime.now(timezone.utc)

app = FastAPI(title="gov-data-poc", version=VERSION)

# ---- 静的 index.html を / と /index.html で配信（存在すれば）----
if (WEB_ROOT / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT), html=True), name="static")

    @app.get("/", include_in_schema=False)
    def root_html():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")

    @app.get("/index.html", include_in_schema=False)
    def index_html():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")
else:
    @app.get("/", include_in_schema=False)
    def root_json():
        return {"ok": True, "service": "gov-data-poc", "version": VERSION}

# ---- 共通：APIトークンチェック（設定されていれば必須）----
def _require(x_api_key: Optional[str]) -> None:
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ---- /health ----
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round((datetime.now(timezone.utc) - START_TS).total_seconds(), 2),
    }

# ---- /ask（ダミー応答）----
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

@app.get("/ask", response_model=AskResponse)
def ask(q: str = Query(...), lang: str = Query("ja"), x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# ---- /feedback（jsonl 追記）----
class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

@app.post("/feedback")
def feedback(body: FeedbackIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)  # 念のため
    out = FEEDBACK_DIR / f"{datetime.utcnow():%Y%m%d}.jsonl"
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": str(out)})

# ---- /admin/reindex（フラグファイル作成）----
@app.post("/admin/reindex")
def admin_reindex(force: bool = True, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)  # 管理操作なので必須
    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    flag = FLAGS_DIR / f"reindex.{ts}.flag"
    flag.write_text("reindex\n", encoding="utf-8")
    return {"ok": True, "flag": str(flag)}
