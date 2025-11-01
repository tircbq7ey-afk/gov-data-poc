from fastapi import FastAPI, Header, HTTPException, Body
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import json
import os

APP = FastAPI(title="gov-data-poc", docs_url="/docs", redoc_url=None)

# --- Paths
WEB_ROOT   = Path(os.getenv("WEB_ROOT", "/app/www")).resolve()
DATA_DIR   = Path(os.getenv("DATA_DIR", "/app/data")).resolve()
FB_DIR     = DATA_DIR / "feedback"
FLAGS_DIR  = DATA_DIR / "flags"

# --- Bootstrapping
for p in (WEB_ROOT, DATA_DIR, FB_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

# --- Simple API key
API_KEY = os.getenv("API_KEY", "changeme-local-token")

def require_api_key(x_api_key: Optional[str]):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")

# --- Health
@APP.get("/health")
def health():
    return {"ok": True, "service": "gov-data-poc", "version": "dev"}

# --- Ask (ダミー実装：そのまま返すだけ)
@APP.get("/ask")
def ask(q: str, lang: str = "ja", sources: Optional[List[str]] = None):
    return {
        "q": q,
        "lang": lang,
        "answer": f"[{lang}] 受領: {q}",
        "sources": sources or [],
    }

# --- Feedback: JSONL 追記
@APP.post("/feedback")
def feedback(
    payload: Dict[str, Any] = Body(...),
    x_api_key: Optional[str] = Header(None)
):
    require_api_key(x_api_key)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {**payload, "ts": ts}
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = FB_DIR / f"{today}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": f"./data/feedback/{out.name}"})

# --- Admin: reindex（ダミー）
#  - すべての JSONL をスキャンして件数を返す
#  - フラグファイル /app/data/flags/reindexed_at.txt を更新
@APP.post("/admin/reindex")
def admin_reindex(
    body: Dict[str, Any] = Body({"force": True}),
    x_api_key: Optional[str] = Header(None)
):
    require_api_key(x_api_key)
    total = 0
    files = sorted(FB_DIR.glob("*.jsonl"))
    for fp in files:
        with fp.open("r", encoding="utf-8") as f:
            for _ in f:
                total += 1

    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    flag = FLAGS_DIR / "reindexed_at.txt"
    flag.write_text(datetime.now(timezone.utc).isoformat(timespec="seconds"), encoding="utf-8")

    return {"ok": True, "indexed_files": len(files), "indexed_records": total, "flag": str(flag)}

# --- 静的トップ（念のため）
@APP.get("/")
def root():
    idx = WEB_ROOT / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return {"ok": True, "service": "gov-data-poc", "version": "dev"}
