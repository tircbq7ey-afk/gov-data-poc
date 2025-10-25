import os, time, json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ==== settings ====
API_TOKEN   = os.getenv("API_TOKEN", "").strip()
VERSION     = os.getenv("VERSION", "dev")
BUILD_TIME  = os.getenv("BUILD_TIME", "unknown")
START_TS    = time.time()

DATA_DIR     = os.getenv("DATA_DIR", "/app/data")
FEEDBACK_DIR = os.path.join(DATA_DIR, "feedback")
FLAGS_DIR    = os.path.join(DATA_DIR, "flags")

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ==== health / root ====
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

# ==== /ask ====
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

# GET /ask
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., title="Q"),
    lang: str = Query("ja", title="Lang"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# POST /ask（PowerShell から JSON で投げる用）
class AskIn(BaseModel):
    q: str
    top_k: int = 3
    min_score: float = 0.2
    lang: str = "ja"

@app.post("/ask", response_model=AskResponse)
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(q=body.q, lang=body.lang, answer=f"[{body.lang}] 受理: {body.q}", sources=[])

# ==== /feedback ====
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
    out_path = os.path.join(FEEDBACK_DIR, f"{datetime.utcnow():%Y%m%d}.jsonl")
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": out_path})

# ==== /admin/reindex ====
class ReindexIn(BaseModel):
    force: bool = False

@app.post("/admin/reindex")
def reindex(body: ReindexIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    os.makedirs(FLAGS_DIR, exist_ok=True)
    flag_file = os.path.join(FLAGS_DIR, "reindex")
    with open(flag_file, "w", encoding="utf-8") as f:
        f.write(datetime.utcnow().isoformat(timespec="seconds") + "Z")
        if body.force:
            f.write("\nforce=true")
    return {"ok": True, "flag": flag_file}
