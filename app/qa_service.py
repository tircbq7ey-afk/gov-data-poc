import os, time, json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

API_TOKEN = os.getenv("API_TOKEN", "").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
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

# ========= ASK =========

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

# 既存：GET /ask
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., title="Q"),
    lang: str = Query("ja", title="Lang"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# 追加：POST /ask（JSONボディ）
class AskIn(BaseModel):
    q: str
    top_k: Optional[int] = 3
    min_score: Optional[float] = 0.2
    lang: str = "ja"

@app.post("/ask", response_model=AskResponse)
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # 実処理は PoC 想定のダミー応答
    return AskResponse(
        q=body.q, lang=body.lang, answer=f"[{body.lang}] 受理: {body.q}", sources=[]
    )

# ========= FEEDBACK =========

class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

@app.post("/feedback")
def feedback(body: FeedbackIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    path = "./data/feedback"
    os.makedirs(path, exist_ok=True)
    out = os.path.join(path, f"{datetime.utcnow():%Y%m%d}.jsonl")
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": out})

# ========= ADMIN =========

class ReindexIn(BaseModel):
    force: bool = False

@app.post("/admin/reindex")
def admin_reindex(
    body: ReindexIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # フラグファイルを置く（PoC想定）
    flags_dir = "./data/flags"
    os.makedirs(flags_dir, exist_ok=True)
    flag_path = os.path.join(flags_dir, f"reindex_{int(time.time())}.flag")
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"force": body.force, "ts": time.time()}))
    return {"ok": True, "flag": flag_path}
