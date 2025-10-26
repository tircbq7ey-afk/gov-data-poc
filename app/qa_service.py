# app/qa_service.py
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

APP_START = time.time()

# ====== 収納パス（コンテナ内）======
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www"))  # index.html 置き場

for d in (FEEDBACK_DIR, FLAGS_DIR, WEB_ROOT):
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="gov-data-poc", version="dev")

# ====== Pydantic モデル ======
class AskResponse(BaseModel):
    q: str = Field(title="Q")
    lang: str = Field(title="Lang")
    answer: str = Field(title="Answer")
    sources: List[str] = Field(default_factory=list, title="Sources")

class FeedbackIn(BaseModel):
    q: str = Field(title="Q")
    answer: str = Field(title="Answer")
    label: str = Field(default="good", title="Label")
    sources: List[str] = Field(default_factory=list, title="Sources")
    lang: Optional[str] = Field(default="ja", title="Lang")
    ts: Optional[str] = Field(default=None, title="Timestamp ISO8601")

class ReindexIn(BaseModel):
    force: bool = True

# ====== ヘルスチェック ======
@app.get("/health", summary="Health")
def health(x_api_key: Optional[str] = Header(default=None)):
    return {
        "ok": True,
        "version": app.version,
        "build_time": "unknown",
        "uptime_sec": round(time.time() - APP_START, 2),
    }

# ====== 既存：GET /ask ======
@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask_get(
    q: str,
    lang: str = "ja",
    x_api_key: Optional[str] = Header(default=None),
):
    # PoC 用の固定応答（必要に応じて検索や LLM 呼び出しに差し替え）
    answer = "オンラインで申請できます。"
    return AskResponse(q=q, lang=lang, answer=answer, sources=[])

# ====== 既存：POST /feedback ======
@app.post("/feedback", summary="Feedback")
def feedback_post(payload: FeedbackIn, x_api_key: Optional[str] = Header(default=None)):
    ts = payload.ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = payload.dict()
    row["ts"] = ts

    fname = datetime.now(timezone.utc).strftime("%Y%m%d") + ".jsonl"
    out = FEEDBACK_DIR / fname
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": str(out)})

# ====== 追加：POST /admin/reindex ======
@app.post("/admin/reindex", summary="Reindex")
def admin_reindex(body: ReindexIn, x_api_key: Optional[str] = Header(default=None)):
    """
    再インデックスのトリガーファイルを /app/data/flags/ に作成
    """
    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    flag = FLAGS_DIR / ("reindex.force" if body.force else "reindex.request")
    flag.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    return {"ok": True, "flag": str(flag)}

# ====== 追加：フロント配信 ======
@app.get("/", include_in_schema=False)
def root():
    # ルートアクセスで /index.html にリダイレクト（API とパスが競合しない安全策）
    return RedirectResponse(url="/index.html", status_code=302)

@app.get("/index.html", include_in_schema=False)
def serve_index():
    index_file = WEB_ROOT / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_file)

# 任意の JS/CSS/画像を /static/* で配信（置き場所は WEB_ROOT）
app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")
