# qa_service.py
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Header, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---- 環境変数とパス ----
APP_PORT = int(os.getenv("APP_PORT", "8010"))
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"
API_TOKEN = os.getenv("API_TOKEN", "").strip()

for p in (WEB_ROOT, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

# 静的ファイルは /static にマウント。/ と /index.html は明示ルートで index.html を返す
if (WEB_ROOT / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT)), name="static")

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

# 共通：x-api-key が必要ならチェック
def _require(x_api_key: Optional[str]) -> None:
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

@app.get("/health", summary="Health")
def health():
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round(time.time() - START_TS, 2),
    }

# --- /ask: 確認用のエコーAPI（そのままでもOK） ---
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask(
    q: str = Query(...),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# --- /feedback: JSONL に追記 ---
class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

@app.post("/feedback", summary="Feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    _require(x_api_key)
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    out = FEEDBACK_DIR / f"{datetime.now(timezone.utc):%Y%m%d}.jsonl"

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": str(out)})

# --- /admin/reindex: フラグ作成（管理操作） ---
@app.post("/admin/reindex", summary="Admin Reindex")
def admin_reindex(
    force: bool = True,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    _require(x_api_key)
    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    flag = FLAGS_DIR / f"reindex.{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.flag"
    flag.write_text("reindex\n", encoding="utf-8")
    return {"ok": True, "flag": str(flag)}
