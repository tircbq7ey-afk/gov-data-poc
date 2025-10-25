import os, json, time, datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token").strip()
VERSION   = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS  = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ---- models
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

class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

# ---- utilities
DATA_DIR    = "./data"
FB_DIR      = os.path.join(DATA_DIR, "feedback")
FLAGS_DIR   = os.path.join(DATA_DIR, "flags")
os.makedirs(FB_DIR, exist_ok=True)
os.makedirs(FLAGS_DIR, exist_ok=True)

# ---- endpoints
@app.get("/health")
def health(x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    return {
        "ok": True,
        "version": VERSION,
        "build_time": BUILD_TIME,
        "uptime_sec": round(time.time() - START_TS, 2),
    }

@app.get("/")
def root(x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    return {"ok": True, "service": "gov-data-poc", "version": VERSION}

# GET /ask（既存の形）
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(...),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # ダミー回答
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# POST /ask（追加）
@app.post("/ask", response_model=AskResponse)
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # 必要なら top_k/min_score を使って検索する実装に差し替え
    return AskResponse(
        q=body.q, lang=body.lang, answer=f"[{body.lang}] 受理: {body.q}", sources=[]
    )

# POST /feedback（既存）
@app.post("/feedback")
def feedback(body: FeedbackIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    out = os.path.join(FB_DIR, f"{datetime.datetime.utcnow():%Y%m%d}.jsonl")
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": out})

# POST /admin/reindex（追加）
@app.post("/admin/reindex")
def admin_reindex(
    body: Dict[str, Any] | None = None,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # フラグを書いて別プロセスに検知させる運用（最小構成）
    flag = os.path.join(FLAGS_DIR, "reindex.touch")
    with open(flag, "w", encoding="utf-8") as f:
        f.write(datetime.datetime.utcnow().isoformat() + "Z")
    return {"ok": True, "flag": flag}
