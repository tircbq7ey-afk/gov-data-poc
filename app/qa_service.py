from __future__ import annotations
import os, json, time
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

API_TOKEN = os.getenv("API_TOKEN", "").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
APP_PORT = int(os.getenv("APP_PORT", "8010"))

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
FEEDBACK_DIR = os.path.join(DATA_DIR, "feedback")

os.makedirs(FEEDBACK_DIR, exist_ok=True)
START_TS = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

@app.get("/health")
def health():
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round(time.time() - START_TS, 2),
    }

@app.get("/")
def root():
    return {"ok": True, "service": "gov-data-poc", "version": VERSION}

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

@app.get("/ask", response_model=AskResponse)
def ask(q: str = Query(...), lang: str = Query("ja"), x_api_key: Optional[str] = Header(None, alias="x-api-key")):
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
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    out = os.path.join(FEEDBACK_DIR, f"{datetime.utcnow():%Y%m%d}.jsonl")
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": out})

# ★ これが無かったため 404 になっていた
class ReindexIn(BaseModel):
    force: bool = False

@app.post("/admin/reindex")
def admin_reindex(body: ReindexIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    # 実処理はダミー。最低限「今日の jsonl があるか」をチェックして件数を返す。
    today = datetime.utcnow().strftime("%Y%m%d")
    path = os.path.join(FEEDBACK_DIR, f"{today}.jsonl")
    count = 0
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for _ in f:
                count += 1
    return {"ok": True, "indexed": count, "feedback_file": path}
