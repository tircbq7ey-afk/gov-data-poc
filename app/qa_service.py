# app/qa_service.py
from __future__ import annotations
import os, json, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# --- env & paths
VERSION   = os.getenv("VERSION", "dev")
API_TOKEN = os.getenv("API_TOKEN", "").strip()  # 使うならヘッダ x-api-key で検証
APP_PORT  = int(os.getenv("APP_PORT", "8010"))

WEB_ROOT  = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR  = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR    = DATA_DIR / "flags"

# ensure dirs
for p in (WEB_ROOT, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

START_TS = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require_token(x_api_key: Optional[str]) -> None:
    """API_TOKEN が設定されている場合のみ検証"""
    if API_TOKEN and (x_api_key or "") != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# --- static: / と /index.html
if (WEB_ROOT / "index.html").exists():
    # 参考: /static でも配れるようにしておく
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT), html=True), name="static")

    @app.get("/", include_in_schema=False)
    def root_html():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")

    @app.get("/index.html", include_in_schema=False)
    def index_alias():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")
else:
    @app.get("/", include_in_schema=False)
    def root_fallback():
        return {"ok": True, "service": "gov-data-poc", "version": VERSION}

# --- health
@app.get("/health", summary="Health")
def health():
    return {
        "ok": True,
        "version": VERSION,
        "build_time": os.getenv("BUILD_TIME", "unknown"),
        "uptime_sec": round(time.time() - START_TS, 2),
    }

# --- demo Q&A
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask(
    q: str = Query(...),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    # 必要なら認証
    _require_token(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# --- feedback
class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

@app.post("/feedback", summary="Feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require_token(x_api_key)

    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = FEEDBACK_DIR / f"{day}.jsonl"

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": f"./data/feedback/{out.name}"})

# --- admin: reindex flag
@app.post("/admin/reindex", summary="Admin Reindex")
def admin_reindex(
    force: bool = True,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require_token(x_api_key)

    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    flag = FLAGS_DIR / f"reindex.{ts}.flag"
    flag.write_text("reindex\n", encoding="utf-8")
    return {"ok": True, "flag": f"./data/flags/{flag.name}"}
