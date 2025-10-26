# app/qa_service.py
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ----- 環境変数 & ディレクトリ準備 -----
APP_PORT = int(os.getenv("APP_PORT", "8010"))
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"
API_TOKEN = os.getenv("API_TOKEN", "")  # 空ならトークンチェック無効

for p in (WEB_ROOT, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

started_at = datetime.now(timezone.utc)

# ----- FastAPI -----
app = FastAPI(title="gov-data-poc", version="dev")

# 静的ファイル（/index.html と / を返す）
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
        return JSONResponse({"ok": True, "service": "gov-data-poc", "version": "dev"})

# ----- 共通 -----
def assert_token(x_api_key: Optional[str]):
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ----- モデル -----
class AskResponse(BaseModel):
    q: str
    lang: str = "ja"
    answer: str
    sources: List[str] = []

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = []
    label: str = "good"   # good / bad など
    lang: str = "ja"

# ----- ヘルス -----
@app.get("/health")
def health():
    uptime = (datetime.now(timezone.utc) - started_at).total_seconds()
    return {"ok": True, "version": "dev", "build_time": "unknown", "uptime_sec": round(uptime, 2)}

# ----- デモ用 Ask（今はダミー応答）-----
@app.get("/ask", response_model=AskResponse)
def ask(q: str = Query(...), lang: str = Query("ja")):
    # ここに本来の検索/LLM 応答を実装
    return AskResponse(q=q, lang=lang, answer="オンラインで申請できます。", sources=[])

# ----- フィードバック保存（JSONL） -----
@app.post("/feedback")
def feedback(body: FeedbackIn, x_api_key: Optional[str] = Header(default=None)):
    # 必要ならトークン必須にする
    assert_token(x_api_key)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    outfile = FEEDBACK_DIR / f"{day}.jsonl"

    rec = {
        "q": body.q,
        "answer": body.answer,
        "sources": body.sources,
        "label": body.label,
        "lang": body.lang,
        "ts": ts,
    }
    outfile.write_text("", encoding="utf-8") if not outfile.exists() else None
    with outfile.open("a", encoding="utf-8") as f:
        f.write(__import__("json").dumps(rec, ensure_ascii=False) + "\n")

    return {"ok": True, "path": str(outfile)}

# ----- 再インデックス用フラグ作成 -----
@app.post("/admin/reindex")
def admin_reindex(force: bool = True, x_api_key: Optional[str] = Header(default=None)):
    assert_token(x_api_key)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    flag = FLAGS_DIR / f"reindex.{ts}.flag"
    try:
        flag.write_text("reindex\n", encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to write flag: {e}")
    return {"ok": True, "flag": str(flag)}
