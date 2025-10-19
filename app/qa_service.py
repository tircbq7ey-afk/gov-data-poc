import os, time, json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ← 環境変数が無ければ "changeme-local-token" を使う
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

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

class ReindexIn(BaseModel):
    force: bool = False

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

# GET /ask
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., title="Q"),
    lang: str = Query("ja", title="Lang"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# POST /ask
@app.post("/ask", response_model=AskResponse)
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(q=body.q, lang=body.lang, answer=f"[{body.lang}] 受理: {body.q}", sources=[])

# POST /feedback → ./data/feedback/YYYYMMDD.jsonl へ追記
@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    base = "/app/data"
    path = os.path.join(base, "feedback")
    os.makedirs(path, exist_ok=True)

    out = os.path.join(path, f"{datetime.utcnow():%Y%m%d}.jsonl")
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ホスト視点の相対パスで返す
    return JSONResponse({"ok": True, "path": f"./data/feedback/{datetime.utcnow():%Y%m%d}.jsonl"})

# POST /admin/reindex → ./data/flags/reindex_*.flag を作成
@app.post("/admin/reindex")
def admin_reindex(
    body: ReindexIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    base = "/app/data"
    flags = os.path.join(base, "flags")
    os.makedirs(flags, exist_ok=True)

    flag_file = os.path.join(flags, f"reindex_{int(time.time())}.flag")
    payload = {"force": body.force, "ts": datetime.utcnow().isoformat() + "Z"}

    with open(flag_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    return {"ok": True, "flag": f"./data/flags/{os.path.basename(flag_file)}"}
