import os
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# -------- settings --------
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)

def _require(x_api_key: Optional[str]) -> None:
    """
    認証が有効なとき(API_TOKENが空でない)は x-api-key を検証。
    """
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

# -------- models --------
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

class ReindexIn(BaseModel):
    force: bool = False

# -------- endpoints --------
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
    q: str = Query(..., title="Q"),
    lang: str = Query("ja", title="Lang"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    # 認証（API_TOKENが設定されている場合のみチェック）
    _require(x_api_key)

    # ここではダミー回答（接続先LLM/ベクタDBがまだ無い前提）
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])

@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)

    # ./data/feedback/ に日毎の jsonl を追記
    path = "./data/feedback"
    os.makedirs(path, exist_ok=True)
    out = os.path.join(path, f"{datetime.utcnow():%Y%m%d}.jsonl")

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": out})

@app.post("/admin/reindex")
def reindex(
    body: ReindexIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)

    # インデックス作成の代わりにフラグファイルを作る
    flags_dir = "./data/flags"
    os.makedirs(flags_dir, exist_ok=True)
    flag_path = os.path.join(flags_dir, "reindexed.ok")

    payload = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "force": body.force,
        "version": VERSION,
    }
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))

    return {
        "ok": True,
        "message": "reindexed",
        "flag": flag_path,
        "payload": payload,
    }

# -------- local run --------
if __name__ == "__main__":
    # uvicorn 起動 (Docker では CMD/ENTRYPOINT で呼ばれる想定でもOK)
    import uvicorn
    uvicorn.run("qa_service:app", host="0.0.0.0", port=8010, reload=False)
