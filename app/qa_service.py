import os
from pathlib import Path
from typing import List, Optional, Literal
from datetime import datetime, timezone

from fastapi import FastAPI, Header, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ====== 環境変数 / パス ======
APP_PORT  = int(os.getenv("APP_PORT", "8010"))
WEB_ROOT  = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR  = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR    = DATA_DIR / "flags"

for p in (WEB_ROOT, DATA_DIR, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

API_TOKEN = os.getenv("API_TOKEN", "")  # 空ならトークン認証を無効化

def assert_token(x_api_key: Optional[str]):
    """管理系などで使う簡易トークン認証"""
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

started_at = datetime.now(timezone.utc)

app = FastAPI(title="gov-data-poc", version="dev")

# ====== 静的配信（/ と /index.html を返す） ======
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

# ====== モデル ======
class AskOut(BaseModel):
    q: str
    lang: str = "ja"
    answer: str
    sources: List[str] = []

class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: Literal["good", "bad"] = "good"
    sources: List[str] = []
    ts: Optional[str] = None  # ISO 文字列で格納

# ====== ヘルスチェック ======
@app.get("/health")
def health():
    return {
        "ok": True,
        "version": "dev",
        "build_time": "unknown",
        "uptime_sec": int((datetime.now(timezone.utc) - started_at).total_seconds()),
    }

# ====== Q&A (ダミー応答) ======
@app.get("/ask", response_model=AskOut)
def ask(
    q: str = Query(..., alias="q", min_length=1),
    lang: str = Query("ja"),
    top_k: int = Query(3, ge=1, le=20),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    # ※必要なら認証を有効化
    # assert_token(x_api_key)

    # ここは PoC 用の固定応答。実装が入れば置き換え。
    answer = "オンラインで申請できます。"
    return AskOut(q=q, lang=lang, answer=answer, sources=[])

# ====== フィードバック ======
@app.post("/feedback")
def feedback(
    fb: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    # ※必要なら認証を有効化
    # assert_token(x_api_key)

    ts = fb.ts or datetime.now(timezone.utc).isoformat()
    rec = {
        "q": fb.q,
        "answer": fb.answer,
        "label": fb.label,
        "sources": fb.sources,
        "ts": ts,
    }

    # yyyymmdd.jsonl に追記
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = FEEDBACK_DIR / f"{day}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(JSONResponse(rec).body.decode("utf-8"))
        f.write("\n")

    return {"ok": True, "path": str(out)}

# ====== 再インデックス用フラグ ======
@app.post("/admin/reindex")
def admin_reindex(
    force: bool = True,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    # 管理操作はトークンチェック
    assert_token(x_api_key)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    flag = FLAGS_DIR / f"reindex.{ts}.flag"
    flag.write_text("reindex\n", encoding="utf-8")
    return {"ok": True, "flag": str(flag)}
