import os
import json
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional

API_TOKEN = os.getenv("API_TOKEN", "")
TEXTS_JSON = os.getenv("TEXTS_JSON", "./data/db/texts.json")
FAQ_JSON = os.getenv("FAQ_JSON", "./data/faq.json")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
FEEDBACK_DIR = os.getenv("FEEDBACK_DIR", "./data/feedback")

app = FastAPI(title="gov-data-poc")

os.makedirs(FEEDBACK_DIR, exist_ok=True)
os.makedirs(os.path.dirname(TEXTS_JSON), exist_ok=True)
os.makedirs(os.path.dirname(FAQ_JSON), exist_ok=True)

def require_api_key(x_api_key: Optional[str]):
    if not API_TOKEN:
        return  # トークン無効化モード（必要なら許可）
    if not x_api_key or x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

class AskResponse(BaseModel):
    q: str
    lang: str
    answer: str
    sources: List[str] = []

class FeedbackIn(BaseModel):
    q: str = Field(..., description="元の質問")
    answer: str = Field(..., description="返答")
    label: str = Field(..., description="good/ok/bad など")
    sources: List[str] = Field(default_factory=list)
    input: dict = Field(default_factory=dict)
    ctx: dict = Field(default_factory=dict)

@app.get("/health")
def health():
    return {"ok": True, "version": os.getenv("VERSION", "dev")}

@app.get("/ask", response_model=AskResponse)
def ask(
    q: str = Query(...),
    lang: str = Query("ja"),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key")
):
    require_api_key(x_api_key)

    # とりあえずダミー回答（必要に応じてFAQ/ベクター検索に差し替え）
    answer = f"[{lang}] 受け付けました: {q}"
    sources = ["https://example.com/a", "/docs/b"]
    return AskResponse(q=q, lang=lang, answer=answer, sources=sources)

@app.post("/feedback")
def feedback(
    body: FeedbackIn,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key")
):
    require_api_key(x_api_key)
    out = body.dict()
    out["ts"] = datetime.utcnow().isoformat() + "Z"
    outpath = os.path.join(FEEDBACK_DIR, f"{datetime.utcnow():%Y%m%d}.jsonl")
    with open(outpath, "a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "path": outpath})
