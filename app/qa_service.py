import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ===== 設定（環境変数で上書き可） =====
APP_PORT = int(os.getenv("APP_PORT", "8010"))
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"
API_TOKEN = os.getenv("API_TOKEN", "")  # 空なら認証無し

for p in (WEB_ROOT, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

started_at = datetime.now(timezone.utc)

app = FastAPI(title="gov-data-poc", version="dev")


# ===== 静的ファイル配信 =====
if (WEB_ROOT / "index.html").exists():
    # /static 配下にマウントし、/ と /index.html は明示返却
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


# ===== 共通 =====
def assert_token(x_api_key: Optional[str]):
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


# ===== モデル =====
class AskOut(BaseModel):
    q: str = Field(title="Q")
    lang: str = Field("ja", title="Lang")
    answer: str = Field(title="Answer")
    sources: List[str] = Field(default_factory=list, title="Sources")


class FeedbackIn(BaseModel):
    q: str = Field(title="Q")
    answer: str = Field(title="Answer")
    label: str = Field("good", title="Label")
    sources: List[str] = Field(default_factory=list, title="Sources")
    lang: Optional[str] = Field("ja", title="Lang")


# ===== ヘルスチェック =====
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": "dev",
        "build_time": "unknown",
        "uptime_sec": round((datetime.now(timezone.utc) - started_at).total_seconds(), 2),
    }


# ===== 検索ダミー（今は簡易実装） =====
@app.get("/ask", response_model=AskOut)
def ask(q: str = Query(..., title="Q"),
        lang: str = Query("ja", title="Lang"),
        x_api_key: Optional[str] = Header(default=None)):
    # 公開エンドポイントなら認証不要にしておく（必要なら assert_token を有効化）
    # assert_token(x_api_key)

    # ここは PoC：実際は RAG 等に置換
    canned = "オンラインで申請できます。"
    return AskOut(q=q, lang=lang, answer=canned, sources=[])


# ===== フィードバック保存（JSONL） =====
@app.post("/feedback")
def feedback(body: FeedbackIn = Body(...),
             x_api_key: Optional[str] = Header(default=None)):
    # 公開で良ければ認証不要。必要なら assert_token を有効化
    # assert_token(x_api_key)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {
        "q": body.q,
        "answer": body.answer,
        "label": body.label,
        "sources": body.sources,
        "lang": body.lang or "ja",
        "ts": ts,
    }
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    fpath = FEEDBACK_DIR / (datetime.now(timezone.utc).strftime("%Y%m%d") + ".jsonl")
    with fpath.open("a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(fpath)}


# ===== 再インデックス要求（フラグファイル作成） =====
@app.post("/admin/reindex")
def admin_reindex(force: bool = True,
                  x_api_key: Optional[str] = Header(default=None)):
    # 管理操作はトークン必須（API_TOKEN 未設定ならスキップ）
    assert_token(x_api_key)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    flag = FLAGS_DIR / f"reindex.{ts}.flag"
    flag.write_text("reindex\n", encoding="utf-8")
    return {"ok": True, "flag": str(flag)}
