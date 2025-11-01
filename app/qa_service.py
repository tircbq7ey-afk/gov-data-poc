# /app/qa_service.py
from __future__ import annotations
import os, time, json
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

API_TOKEN = os.getenv("API_TOKEN", "").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

# base paths (コンテナ内)
ROOT_DIR = "/app"
DATA_DIR = os.path.join(ROOT_DIR, "data")
FEEDBACK_DIR = os.path.join(DATA_DIR, "feedback")
FLAGS_DIR = os.path.join(DATA_DIR, "flags")

# 必要なディレクトリを起動時に作成
for p in (DATA_DIR, FEEDBACK_DIR, FLAGS_DIR):
    os.makedirs(p, exist_ok=True)

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    # API_TOKEN を設定した場合のみチェックする（未設定ならスキップ）
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

# --- /ask: ダミー回答（今はスタブ） ---
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

@app.get("/ask", response_model=AskResponse)
def ask(q: str = Query(...), lang: str = Query("ja"), x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    # 実サービス実装前はスタブ回答
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# --- /feedback: JSONL 追記 ---
class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

@app.post("/feedback")
def feedback(body: FeedbackIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    # 日付別 jsonl
    fn = datetime.utcnow().strftime("%Y%m%d") + ".jsonl"
    out = os.path.join(FEEDBACK_DIR, fn)
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": f"./data/feedback/{fn}"})

# --- /admin/reindex: インデックス再構築トリガ（フラグファイルを作成） ---
class ReindexIn(BaseModel):
    force: bool = False

@app.post("/admin/reindex")
def admin_reindex(body: ReindexIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    os.makedirs(FLAGS_DIR, exist_ok=True)
    flag = os.path.join(FLAGS_DIR, "reindexed_at.txt")
    with open(flag, "w", encoding="utf-8") as f:
        f.write(datetime.utcnow().isoformat(timespec="seconds") + "Z")
        if body.force:
            f.write("\nforce=true")
    return {"ok": True, "flag": "/app/data/flags/reindexed_at.txt"}
