import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ==== 環境変数・パス ====
APP_PORT = int(os.getenv("APP_PORT", "8010"))
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"

for p in (WEB_ROOT, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

started_at = datetime.now(timezone.utc)

# ==== FastAPI ====
app = FastAPI(title="gov-data-poc", version="dev")

# ---- static: / と /index.html を返す ----
if (WEB_ROOT / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT), html=True), name="static")

    @app.get("/", include_in_schema=False)
    async def root():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")

    @app.get("/index.html", include_in_schema=False)
    async def index_alias():
        return FileResponse(WEB_ROOT / "index.html", media_type="text/html")
else:
    @app.get("/", include_in_schema=False)
    async def root_not_found():
        return JSONResponse({"ok": False, "detail": "index.html not found"}, status_code=404)

# ---- 認証（管理系のみ） ----
def assert_token(x_api_key: Optional[str]):
    token = os.getenv("API_TOKEN", "")
    if token and x_api_key != token:
        raise HTTPException(status_code=401, detail="unauthorized")

# ==== Schemas ====
class AskResponse(BaseModel):
    q: str = Field(title="Q")
    lang: str = Field(default="ja", title="Lang")
    answer: str = Field(title="Answer")
    sources: List[str] = Field(default_factory=list, title="Sources")

class FeedbackIn(BaseModel):
    q: str = Field(title="Q")
    answer: str = Field(title="Answer")
    label: str = Field(default="good", title="Label")
    sources: List[str] = Field(default_factory=list, title="Sources")
    lang: str = Field(default="ja", title="Lang")

# ==== Endpoints ====
@app.get("/health")
def health():
    uptime = (datetime.now(timezone.utc) - started_at).total_seconds()
    return {"ok": True, "version": "dev", "build_time": "unknown", "uptime_sec": round(uptime, 2)}

@app.get("/ask", response_model=AskResponse)
def ask(q: str = Query(...), lang: str = Query("ja")):
    # ここは PoC 用のダミー応答
    return AskResponse(q=q, lang=lang, answer="オンラインで申請できます。", sources=[])

@app.post("/feedback")
def feedback(payload: FeedbackIn = Body(...)):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = FEEDBACK_DIR / f"{ts}.jsonl"
    line = payload.model_dump()
    line["ts"] = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as f:
        f.write(JSONResponse(content=line).body.decode("utf-8") + "\n")
    return {"ok": True, "path": str(path)}

@app.post("/admin/reindex")
def admin_reindex(force: bool = True, x_api_key: Optional[str] = Header(default=None)):
    assert_token(x_api_key)  # API_TOKEN を設定している場合のみチェック
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    flag = FLAGS_DIR / f"reindex.{ts}.flag"
    flag.write_text("reindex\n", encoding="utf-8")
    return {"ok": True, "flag": str(flag)}
