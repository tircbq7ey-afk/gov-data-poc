# /app/qa_service.py
import os, time, json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# .env or docker-compose の環境変数で上書き可
API_TOKEN  = os.getenv("API_TOKEN", "changeme-local-token").strip()
VERSION    = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS   = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

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

@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(...),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    base = "./data"
    fb_dir = os.path.join(base, "feedback")
    os.makedirs(fb_dir, exist_ok=True)
    out = os.path.join(fb_dir, f"{datetime.utcnow():%Y%m%d}.jsonl")
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": out})

@app.post("/admin/reindex")
def reindex(
    body: Dict[str, Any] | None = None,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    base = "./data"
    fb_dir = os.path.join(base, "feedback")
    flag_dir = os.path.join(base, "flags")
    os.makedirs(flag_dir, exist_ok=True)
    count = 0
    if os.path.isdir(fb_dir):
        for name in os.listdir(fb_dir):
            if name.endswith(".jsonl"):
                count += 1
    flag_path = os.path.join(flag_dir, "reindexed.ok")
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.utcnow().isoformat()+"Z","files":count}))
    return {"ok": True, "reindexed_files": count, "flag": flag_path}
