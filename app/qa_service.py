import os
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ====== env / meta ======
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    """Simple header based auth (x-api-key)."""
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# ====== health / root ======
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

# ====== schemas ======
class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

class AskIn(BaseModel):
    q: str
    lang: str = "ja"
    top_k: int = 3
    min_score: float = 0.2

class FeedbackIn(BaseModel):
    q: str
    answer: str
    label: str = "good"
    sources: List[str] = Field(default_factory=list)
    lang: str = "ja"

class ReindexIn(BaseModel):
    force: bool = False

# ====== /ask GET (既存) ======
@app.get("/ask", response_model=AskResponse)
def ask_get(
    q: str = Query(..., description="Query"),
    lang: str = Query("ja", description="Lang"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

# ====== /ask POST（追加） ======
@app.post("/ask", response_model=AskResponse)
def ask_post(
    body: AskIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # ここでは PoC としてエコー応答。実サービスに合わせて検索/生成へ差し替え可
    return AskResponse(
        q=body.q,
        lang=body.lang,
        answer=f"[{body.lang}] 受理: {body.q}",
        sources=[],
    )

# ====== /feedback（既存＋堅牢化） ======
@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    base = "./data"
    path = os.path.join(base, "feedback")
    os.makedirs(path, exist_ok=True)

    out = os.path.join(path, f"{datetime.utcnow():%Y%m%d}.jsonl")

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Windows/日本語環境での文字化けを避けるため ensure_ascii=False
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": out})

# ====== /admin/reindex（追加） ======
@app.post("/admin/reindex")
def admin_reindex(
    body: ReindexIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # フラグファイルを切って外部ジョブ/バッチが拾う想定
    base = "./data"
    flags_dir = os.path.join(base, "flags")
    os.makedirs(flags_dir, exist_ok=True)

    flag_path = os.path.join(
        flags_dir, f"reindex.{datetime.utcnow():%Y%m%dT%H%M%SZ}{'.force' if body.force else ''}.flag"
    )
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"force": body.force, "ts": datetime.utcnow().isoformat()+"Z"}))

    return {"ok": True, "flag": flag_path}
