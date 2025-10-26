# app/qa_service.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

APP_DIR = Path("/app")
DATA_DIR = APP_DIR / "data"
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"
WWW_DIR = APP_DIR / "www"

API_KEY_HEADER = "x-api-key"
LOCAL_DEV_API_KEY = "changeme-local-token"  # サンプル固定キー（デモ用途）

app = FastAPI(title="gov-data-poc", version="dev")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- モデル ---------
class AskResponse(BaseModel):
    q: str = Field(..., title="Q")
    lang: str = Field("ja", title="Lang")
    answer: str = Field("", title="Answer")
    sources: List[str] = Field(default_factory=list, title="Sources")


class FeedbackIn(BaseModel):
    q: str = Field(..., title="Q")
    answer: str = Field(..., title="Answer")
    label: str = Field("good", title="Label")
    sources: List[str] = Field(default_factory=list, title="Sources")
    lang: str = Field("ja", title="Lang")


class ReindexIn(BaseModel):
    force: bool = True


# --------- ユーティリティ ---------
def ensure_dirs() -> None:
    for d in (DATA_DIR, FEEDBACK_DIR, FLAGS_DIR, WWW_DIR):
        d.mkdir(parents=True, exist_ok=True)


def require_api_key(x_api_key: Optional[str]) -> None:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing x-api-key")
    if x_api_key != LOCAL_DEV_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid x-api-key")


# --------- 静的ファイル・ルート ---------
# /app/www を / にマウント。index.html をデフォルトにしたいので下のルートも用意。
app.mount("/",
          StaticFiles(directory=str(WWW_DIR), html=True),
          name="www")

@app.get("/", include_in_schema=False)
def root():
    # / → /index.html
    index = WWW_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "welcome", "tip": "Put index.html under /app/www"}, status_code=200)

@app.get("/index.html", include_in_schema=False)
def index_html():
    index = WWW_DIR / "index.html"
    if not index.exists():
        raise HTTPException(404, "index.html not found")
    return FileResponse(str(index))


# --------- ヘルス ---------
@app.get("/health", summary="Health")
def health(x_api_key: Optional[str] = Header(None, alias=API_KEY_HEADER)):
    # NOTE: ヘルスはAPIキー不要にしてもよい。必要なら上の require_api_key を呼ぶ。
    return {"ok": True, "version": "dev", "build_time": "unknown"}


# --------- GET /ask ---------
@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask(
    q: str = Query(..., description="query text"),
    lang: str = Query("ja", description="language code"),
    x_api_key: Optional[str] = Header(None, alias=API_KEY_HEADER),
):
    require_api_key(x_api_key)
    # ダミー応答（PoC）
    ans = "オンラインで申請できます。"
    return AskResponse(q=q, lang=lang, answer=ans, sources=[])


# --------- POST /feedback ---------
@app.post("/feedback", summary="Feedback")
def feedback(
    payload: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias=API_KEY_HEADER),
):
    require_api_key(x_api_key)
    ensure_dirs()

    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    today = datetime.utcnow().strftime("%Y%m%d")
    out = {
        "q": payload.q,
        "answer": payload.answer,
        "label": payload.label,
        "sources": payload.sources,
        "lang": payload.lang,
        "ts": ts,
    }

    path = FEEDBACK_DIR / f"{today}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")

    return {"ok": True, "path": f"./data/feedback/{today}.jsonl"}


# --------- POST /admin/reindex ---------
@app.post("/admin/reindex", summary="Reindex")
def admin_reindex(
    body: ReindexIn,
    x_api_key: Optional[str] = Header(None, alias=API_KEY_HEADER),
):
    require_api_key(x_api_key)
    ensure_dirs()

    # フラグファイル作成（ETLやバッチ側が監視している想定）
    flag = FLAGS_DIR / ("force.reindex" if body.force else "reindex")
    flag.write_text(datetime.utcnow().isoformat() + "Z", encoding="utf-8")

    return {"ok": True, "flag": str(flag)}
