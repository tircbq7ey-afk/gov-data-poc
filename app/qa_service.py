from __future__ import annotations

import os, time, json
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

API_TOKEN  = os.getenv("API_TOKEN", "").strip()
VERSION    = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS   = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    # ローカルで API_TOKEN を空にしている場合は認証スキップ
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round(time.time() - START_TS, 2),
    }

@app.get("/")
def root() -> Dict[str, Any]:
    return {"ok": True, "service": "gov-data-poc", "version": VERSION}

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(...),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
) -> AskResponse:
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    lang: str = "ja"
    sources: List[str] = Field(default_factory=list)

@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    path = "./data/feedback"
    os.makedirs(path, exist_ok=True)
    out = os.path.join(path, f"{datetime.utcnow():%Y%m%d}.jsonl")

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": out})

# ★ 追加: 管理用のダミー reindex エンドポイント
@app.post("/admin/reindex")
def admin_reindex(
    force: bool = False,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    flags_dir = "./data/flags"
    os.makedirs(flags_dir, exist_ok=True)
    marker = os.path.join(flags_dir, "reindexed_at.txt")
    with open(marker, "w", encoding="utf-8") as f:
        f.write(datetime.utcnow().isoformat(timespec="seconds") + "Z")
    return {"ok": True, "force": force, "marker": marker}
