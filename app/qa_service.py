# qa_service.py
from fastapi import FastAPI, Query, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json

app = FastAPI(title="gov-data-poc", version="dev")

# ====== モデル ======
class AskIn(BaseModel):
    q: str = Field(..., title="q")
    top_k: int = Field(3, ge=1, le=50, title="TopK")
    min_score: float = Field(0.2, ge=0.0, le=1.0, title="MinScore")
    lang: str = Field("ja", title="Lang")

class Source(BaseModel):
    id: Optional[str] = Field(None, title="Location")
    score: Optional[float] = None
    meta: Optional[Dict[str, Any]] = None

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[Source] = []

class FeedbackIn(BaseModel):
    q: str
    answer: str
    sources: List[str] = []
    lang: str = "ja"

# ====== ヘルスチェック ======
@app.get("/health", summary="Health")
def health():
    return {
        "ok": True,
        "version": "dev",
        "build_time": "unknown",
        "uptime_sec": 0,  # 簡易
    }

# ====== /ask (GET) ======
@app.get("/ask", response_model=AskResponse, summary="Ask")
def ask_get(
    q: str = Query(..., description="query"),
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.2, ge=0.0, le=1.0),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    # TODO: ここで実際の検索を呼び出す
    answer = "[ja] 受理: " + q
    return AskResponse(q=q, lang=lang, answer=answer, sources=[])

# ====== /ask (POST; JSON) ======
@app.post("/ask", response_model=AskResponse, summary="Ask (POST)")
def ask_post(payload: AskIn, x_api_key: Optional[str] = Header(default=None, alias="x-api-key")):
    # TODO: ここで実際の検索を呼び出す
    answer = f"[{payload.lang}] 受理: {payload.q}"
    return AskResponse(q=payload.q, lang=payload.lang, answer=answer, sources=[])

# ====== /feedback (POST) ======
@app.post("/feedback", summary="Feedback")
def feedback(payload: FeedbackIn, x_api_key: Optional[str] = Header(default=None, alias="x-api-key")):
    out_dir = Path("./data/feedback")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{datetime.utcnow():%Y%m%d}.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload.dict(), ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(out_path)}

# ====== /admin/reindex (POST) ======
@app.post("/admin/reindex", summary="Reindex")
def admin_reindex(x_api_key: Optional[str] = Header(default=None, alias="x-api-key")):
    # TODO: 実データを再読み込みする処理をここに実装
    # ここではダミーで成功を返す
    return {"ok": True, "indexed_docs": 0}
