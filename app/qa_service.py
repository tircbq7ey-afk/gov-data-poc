import os
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# =========================
# Settings
# =========================
API_TOKEN = os.getenv("API_TOKEN", "changeme-local-token").strip()
VERSION = os.getenv("VERSION", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
START_TS = time.time()

app = FastAPI(title="gov-data-poc", version=VERSION)


def _require(x_api_key: Optional[str]) -> None:
    # API_TOKEN が空でなければチェック。空なら認証不要。
    if API_TOKEN and x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


# =========================
# Models
# =========================
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


# =========================
# Routes
# =========================
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


# /ask は GET のみ（POST は 405 になります）
@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask(
    q: str = Query(..., title="Q"),
    lang: str = Query("ja", title="Lang"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)
    # ここは PoC：質問をそのままエコーするダミー回答
    return AskResponse(q=q, lang=lang, answer=f"[{lang}] 受理: {q}", sources=[])


@app.post("/feedback", summary="Feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)

    # 保存先: ./data/feedback/YYYYMMDD.jsonl （ホストに bind mount）
    base = "./data/feedback"
    os.makedirs(base, exist_ok=True)
    out = os.path.join(base, f"{datetime.utcnow():%Y%m%d}.jsonl")

    rec: Dict[str, Any] = body.model_dump()
    rec["ts"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return JSONResponse({"ok": True, "path": out})


# 追加: /admin/reindex を POST で提供
@app.post("/admin/reindex", summary="Reindex")
def reindex(
    body: ReindexIn = Body(default=ReindexIn()),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    _require(x_api_key)

    # reindex のフラグディレクトリを必ず作成
    flags_dir = "./data/flags"
    os.makedirs(flags_dir, exist_ok=True)

    # フラグファイル（タイムスタンプ付き）を作るだけの簡易実装
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    flag_name = f"reindex-{ts}{'-force' if body.force else ''}.flag"
    flag_path = os.path.join(flags_dir, flag_name)

    with open(flag_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "force": body.force}))

    # ついでに feedback ファイルの一覧を返す（確認用）
    feedback_dir = "./data/feedback"
    files = []
    if os.path.isdir(feedback_dir):
        files = sorted(
            [os.path.join(feedback_dir, x) for x in os.listdir(feedback_dir)],
            reverse=True,
        )

    return JSONResponse(
        {
            "ok": True,
            "flag": flag_path,
            "feedback_files": files,
        }
    )
