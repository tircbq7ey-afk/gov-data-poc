# app/qa_service.py
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

APP_PORT = int(os.getenv("APP_PORT", "8010"))
WEB_ROOT = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token")  # プロキシから渡すトークン

for p in (WEB_ROOT, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="gov-data-poc", version="dev")

# ---- index.html 配信（/ と /index.html） ----
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
    async def no_index():
        return JSONResponse({"ok": True, "service": "gov-data-poc", "version": "dev"})

# ---- 共通：トークン検証（設定されている場合のみ） ----
def assert_token(x_api_key: Optional[str]):
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ---- ヘルスチェック ----
@app.get("/health")
def health():
    return {"ok": True, "version": "dev", "build_time": "unknown"}

# ---- デモの /ask（手元確認用のダミー）----
@app.get("/ask")
def ask(q: str, lang: str = "ja", x_api_key: Optional[str] = Header(default=None)):
    # 必要なら保護
    # assert_token(x_api_key)
    return {"q": q, "lang": lang, "answer": "[ja] あくまでデモ応答", "sources": []}

# ---- フィードバック保存（JSONL 追記）----
@app.post("/feedback")
def post_feedback(
    payload: Dict[str, Any] = Body(...),
    x_api_key: Optional[str] = Header(default=None),
):
    # 必要なら保護
    # assert_token(x_api_key)

    # 入力正規化（最低限）
    q = str(payload.get("q", "")).strip()
    answer = str(payload.get("answer", "")).strip()
    sources = payload.get("sources", [])
    label = payload.get("label", "good")
    lang = payload.get("lang", "ja")

    if not q or not answer:
        raise HTTPException(status_code=422, detail="q and answer are required")

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = {
        "q": q,
        "answer": answer,
        "label": label,
        "sources": sources if isinstance(sources, list) else [sources],
        "lang": lang,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    path = FEEDBACK_DIR / f"{today}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        import json
        f.write(json.dumps(out, ensure_ascii=False) + "\n")

    return {"ok": True, "path": str(path)}

# ---- 再インデックス要求：フラグファイル作成 ----
@app.post("/admin/reindex")
def admin_reindex(
    force: bool = True,
    x_api_key: Optional[str] = Header(default=None),
):
    assert_token(x_api_key)  # 管理操作なのでトークン必須にする

    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    flag = FLAGS_DIR / f"reindex.{ts}.flag"
    flag.write_text("reindex\n", encoding="utf-8")
    return {"ok": True, "flag": str(flag)}
