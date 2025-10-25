import os, json, time, datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token").strip()
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

# --------- /ask (GET) ----------
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(..., description="質問"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # ここではダミー応答。実サービスをつなぐなら差し替え。
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# --------- /feedback (POST) ----------
class FeedbackIn(BaseModel):
    q: str
    answer: str
    lang: str = "ja"
    label: str = "good"          # 任意
    sources: List[str] = Field(default_factory=list)

@app.post("/feedback")
def feedback(body: FeedbackIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    base = "./data"
    fb_dir = os.path.join(base, "feedback")
    os.makedirs(fb_dir, exist_ok=True)

    out = os.path.join(fb_dir, f"{datetime.datetime.utcnow():%Y%m%d}.jsonl")
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": out})

# --------- /admin/reindex (POST) ----------
class ReindexIn(BaseModel):
    force: bool = False

@app.post("/admin/reindex")
def reindex(body: ReindexIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    base = "./data"
    flags_dir = os.path.join(base, "flags")
    os.makedirs(flags_dir, exist_ok=True)

    flag_path = os.path.join(
        flags_dir, f"reindex-{datetime.datetime.utcnow():%Y%m%dT%H%M%S}Z.flag"
    )
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"force": body.force, "ts": time.time()}))

    return {"ok": True, "flag": flag_path}
