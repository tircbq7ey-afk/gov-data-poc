# app/qa_service.py
from __future__ import annotations

import os
import json
import time
from typing import Optional, List, Dict, Any

from datetime import datetime
from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

API_TOKEN = os.getenv("API_TOKEN", "").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

DATA_DIR = os.getenv("DATA_DIR", "./data")
FEEDBACK_DIR = os.path.join(DATA_DIR, "feedback")
FLAGS_DIR = os.path.join(DATA_DIR, "flags")
os.makedirs(FEEDBACK_DIR, exist_ok=True)
os.makedirs(FLAGS_DIR, exist_ok=True)

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


# ---------- /ask ----------
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)


class AskIn(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2
    lang: str = "ja"


@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="問い合わせ"),
    lang: str = Query("ja", description="言語"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # ここは PoC のダミー回答
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])


@app.post("/ask", response_model=AskResponse)
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # ここは PoC のダミー回答
    return AskResponse(q=body.q, lang=body.lang, answer=f"[{body.lang}] 受理: {body.q}", sources=[])


# ---------- /feedback ----------
class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"
    label: str = "good"


@app.post("/feedback")
def feedback(body: FeedbackIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    # 1行JSON（.jsonl）で追記
    fname = datetime.utcnow().strftime("%Y%m%d") + ".jsonl"
    out = os.path.join(FEEDBACK_DIR, fname)

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": f"./data/feedback/{fname}"})


# ---------- /admin/reindex ----------
class ReindexIn(BaseModel):
    force: bool = False


@app.post("/admin/reindex")
def admin_reindex(body: ReindexIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    # フィードバック件数を数えて "reindexed.json" を更新（PoC の擬似処理）
    count = 0
    if os.path.isdir(FEEDBACK_DIR):
        for name in os.listdir(FEEDBACK_DIR):
            if name.endswith(".jsonl"):
                count += sum(1 for _ in open(os.path.join(FEEDBACK_DIR, name), encoding="utf-8"))

    stamp = {
        "ok": True,
        "force": body.force,
        "count": count,
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    os.makedirs(FLAGS_DIR, exist_ok=True)
    with open(os.path.join(FLAGS_DIR, "reindexed.json"), "w", encoding="utf-8") as f:
        json.dump(stamp, f, ensure_ascii=False, indent=2)

    return stamp
