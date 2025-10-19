import os, json, time
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

API_TOKEN = os.getenv("API_TOKEN", "").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

# 収集先ディレクトリ（docker-compose で ./data を /app/data にマウント）
DATA_DIR = "/app/data"
FEEDBACK_DIR = os.getenv("FEEDBACK_DIR", f"{DATA_DIR}/feedback")
FLAGS_DIR = f"{DATA_DIR}/flags"

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

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = Field(default_factory=list)

@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(..., description="Query"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # ここはダミー応答（バックエンド検索を繋げるまではプレースホルダ）
    ans = f"[{lang}] 受理: {q}"
    return AskResponse(q=q, lang=lang, answer=ans, sources=[])

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
    out = os.path.join(FEEDBACK_DIR, f"{datetime.utcnow():%Y%m%d}.jsonl")
    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": f"./data/feedback/{os.path.basename(out)}"})

# --- 追加: 再インデックス用の簡易エンドポイント ---
class ReindexIn(BaseModel):
    force: bool = False

@app.post("/admin/reindex")
def admin_reindex(body: ReindexIn, x_api_key: Optional[str] = Header(None, alias="x-api-key")):
    _require(x_api_key)
    os.makedirs(FLAGS_DIR, exist_ok=True)
    flag = os.path.join(FLAGS_DIR, f"reindex_{datetime.utcnow():%Y%m%d_%H%M%S}.txt")
    with open(flag, "w", encoding="utf-8") as f:
        f.write(json.dumps({"force": body.force, "ts": datetime.utcnow().isoformat() + "Z"}))
    # 本番ではここで実際の再インデックス処理を呼び出す
    return {"ok": True, "flag": f"./data/flags/{os.path.basename(flag)}"}
