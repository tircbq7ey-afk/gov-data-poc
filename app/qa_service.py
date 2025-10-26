# app/qa_service.py
from __future__ import annotations
import os, time, json
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path

# ====== 設定 ======
API_TOKEN  = os.getenv("API_TOKEN", "").strip()
VERSION    = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS   = time.time()

# index.html のルート（デフォルト /app/www）
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
WEB_ROOT.mkdir(parents=True, exist_ok=True)

# フィードバック保存先
DATA_DIR      = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR  = DATA_DIR / "feedback"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ====== 健康/ルート ======
@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round(time.time() - START_TS, 2),
    }

# --- 静的ファイル：/ と /index.html で index.html を返す ---
if (WEB_ROOT / "index.html").exists():
    # /static でディレクトリ配信（css/js など）
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT), html=True), name="static")

    @app.get("/", include_in_schema=False)
    def root_html():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")

    @app.get("/index.html", include_in_schema=False)
    def index_html():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")
else:
    # 置いてない場合は従来どおり JSON
    @app.get("/", include_in_schema=False)
    def root_fallback():
        return {"ok": True, "service": "gov-data-poc", "version": VERSION}

# ====== API 本体（ダミー実装） ======
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

@app.get("/ask", response_model=AskResponse)
def ask(q: str = Query(...), lang: str = Query("ja"),
        x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

@app.post("/feedback")
def feedback(body: FeedbackIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    out = FEEDBACK_DIR / f"{datetime.utcnow():%Y%m%d}.jsonl"
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": f"./data/feedback/{out.name}"})
