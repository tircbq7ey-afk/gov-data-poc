# qa_service.py  v1.4.0
# - ログ出力(logs/qa.log, JSONL/ローテーション)
# - /metrics 追加（簡易カウンタ）
# - /batch-ask 追加（CSV→回答CSV）
# - 既存APIは互換: /__version /health /reload /search /ask
from __future__ import annotations

import os
import io
import csv
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import faiss                   # pip install faiss-cpu
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse, StreamingResponse
from starlette.staticfiles import StaticFiles

# ========= 基本設定 =========
APP_VERSION = "1.4.0"
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DB_DIR = DATA_DIR / "db"
PARSED_DIR = DATA_DIR / "parsed"
STATIC_DIR = ROOT_DIR / "static"
INDEX_HTML = ROOT_DIR / "index.html"

TEXTS_PATH = DB_DIR / "texts.json"
INDEX_PATH = DB_DIR / "faiss.index"
DOC_MAP_PATH = DB_DIR / "doc_map.json"
ID_MAP_PATH = DB_DIR / "id_map.json"  # 任意

# しきい値・TopK 既定値（環境変数で上書き可）
TOPK_DEFAULT = int(os.getenv("TOPK_DEFAULT", "5"))
MIN_SCORE_DEFAULT = float(os.getenv("MIN_SCORE", "0.20"))

# OpenAI
from openai import OpenAI
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ========= ロガー =========
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log = logging.getLogger("qa")
log.setLevel(logging.INFO)
if not log.handlers:
    h = RotatingFileHandler(LOG_DIR / "qa.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    f = logging.Formatter('%(message)s')  # JSONL をそのまま書く
    h.setFormatter(f)
    log.addHandler(h)

def _j(d: Dict[str, Any]) -> str:
    return json.dumps(d, ensure_ascii=False, separators=(",", ":"))

# ========= DB 読み込み =========
_global_index: Optional[faiss.Index] = None
_texts: List[Dict[str, Any]] = []
_id_map: Dict[int, int] = {}
_doc_map: Dict[str, Any] = {}
_dim = 1536  # text-embedding-3-small

def load_json(p: Path) -> Any:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_db() -> Tuple[faiss.Index, List[Dict[str, Any]], Dict[int, int], Dict[str, Any]]:
    if not TEXTS_PATH.exists() or not INDEX_PATH.exists():
        raise HTTPException(status_code=503, detail="DB not ready. run parse/embed first.")

    texts = load_json(TEXTS_PATH)
    id_map = load_json(ID_MAP_PATH) if ID_MAP_PATH.exists() else {}
    doc_map = load_json(DOC_MAP_PATH) if DOC_MAP_PATH.exists() else {}

    index = faiss.read_index(str(INDEX_PATH))
    if index.d != _dim:
        raise HTTPException(status_code=500, detail=f"index dim mismatch: {index.d} != {_dim}")

    return index, texts, id_map, doc_map

def _startup():
    global _global_index, _texts, _id_map, _doc_map
    _global_index, _texts, _id_map, _doc_map = load_db()

def _ensure_ready():
    if _global_index is None:
        _startup()

# ========= 埋め込み =========
def _get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 未設定です。")
    return OpenAI(api_key=OPENAI_API_KEY)

def embed_query(q: str) -> np.ndarray:
    client = _get_client()
    e = client.embeddings.create(model=EMBED_MODEL, input=q)
    v = np.array(e.data[0].embedding, dtype=np.float32)
    v = v / (np.linalg.norm(v) + 1e-12)
    return v.reshape(1, -1)

# ========= 検索 =========
def search_top_k(query: str, k: int, min_score: float) -> List[Dict[str, Any]]:
    _ensure_ready()
    qv = embed_query(query)  # (1, dim)
    D, I = _global_index.search(qv, k)  # scores, ids
    out: List[Dict[str, Any]] = []
    for score, idx in zip(D[0], I[0]):
        if idx < 0:
            continue
        if float(score) < min_score:
            continue
        rec = _texts[idx]
        item = {
            "id": rec.get("id"),
            "score": float(score),
            "title": rec.get("title") or "",
            "snippet": rec.get("snippet") or "",
            "source_url": rec.get("source_url") or "",
            "source_path": rec.get("source_path") or "",
        }
        out.append(item)
    return out

# ========= 要約（OpenAI Chat） =========
def summarize_answer(query: str, results: List[Dict[str, Any]]) -> str:
    """シンプルな system+user で要約（コンテキストが無ければ定型返答）"""
    if not OPENAI_API_KEY:
        # APIキーなし時のフォールバック
        if results:
            return "検索結果に基づき回答を生成するには OPENAI_API_KEY を設定してください。"
        else:
            return "該当情報が見つかりませんでした。"
    if not results:
        return "該当情報が見つかりませんでした。"
    # プロンプト
    src = "\n".join([f"- {r['title']}\n  {r['snippet']}" for r in results])
    messages = [
        {"role": "system", "content": "あなたは日本の公的情報に詳しいアシスタントです。根拠の不明な推測はせず、わかる範囲で簡潔に日本語で答えてください。"},
        {"role": "user", "content": f"質問: {query}\n\n参考資料:\n{src}\n\n上記に基づき、箇条書きで簡潔に回答してください。"}
    ]
    client = _get_client()
    chat = client.chat.completions.create(model=os.getenv("CHAT_MODEL", "gpt-4o-mini"), messages=messages, temperature=0.2)
    return chat.choices[0].message.content.strip()

# ========= ロギング/メトリクス =========
_metrics = {
    "requests_total": 0,
    "search_total": 0,
    "ask_total": 0,
    "reload_total": 0,
}

def log_event(kind: str, request: Request, payload: Dict[str, Any]) -> None:
    _metrics["requests_total"] += 1
    if kind == "search":
        _metrics["search_total"] += 1
    elif kind == "ask":
        _metrics["ask_total"] += 1
    elif kind == "reload":
        _metrics["reload_total"] += 1

    try:
        row = {
            "ts": int(time.time()),
            "kind": kind,
            "ip": request.client.host if request and request.client else None,
            **payload,
        }
        log.info(_j(row))
    except Exception:
        pass

# ========= FastAPI =========
app = FastAPI(title="gov-qa service", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False
)

# 静的: index.html（同ディレクトリに配置）
if INDEX_HTML.exists():
    @app.get("/", include_in_schema=False)
    def root():
        return FileResponse(str(INDEX_HTML), media_type="text/html")
else:
    @app.get("/", include_in_schema=False)
    def root():
        return PlainTextResponse("Place index.html next to qa_service.py", status_code=200)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

@app.get("/__version")
def version():
    return PlainTextResponse(f"qa_service {APP_VERSION}")

@app.get("/health")
def health():
    ok = TEXTS_PATH.exists() and INDEX_PATH.exists()
    return JSONResponse({"ok": ok, "index_exists": INDEX_PATH.exists(), "texts_exists": TEXTS_PATH.exists(),
                         "min_score": MIN_SCORE_DEFAULT, "top_k_default": TOPK_DEFAULT})

@app.get("/reload")
def reload_db(request: Request):
    _startup()
    log_event("reload", request, {"ok": True})
    return PlainTextResponse("ok", status_code=200)

@app.get("/metrics")
def metrics():
    return JSONResponse(_metrics)

# ===== /search =====
@app.get("/search")
def api_search(
    request: Request,
    q: str = Query(..., description="検索クエリ"),
    top_k: int = Query(TOPK_DEFAULT, ge=1, le=50, description="上位件数"),
    min_score: float = Query(MIN_SCORE_DEFAULT, ge=0.0, le=1.0, description="最低スコア"),
):
    t0 = time.time()
    try:
        results = search_top_k(q, top_k, min_score)
        dt = time.time() - t0
        log_event("search", request, {"q": q, "top_k": top_k, "min_score": min_score, "count": len(results), "dt_ms": int(dt*1000)})
        return JSONResponse({"ok": True, "query": q, "count": len(results), "min_score": min_score, "results": results})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== /ask =====
@app.get("/ask")
def api_ask(
    request: Request,
    q: str = Query(..., description="質問文"),
    top_k: int = Query(TOPK_DEFAULT, ge=1, le=50),
    min_score: float = Query(MIN_SCORE_DEFAULT, ge=0.0, le=1.0),
):
    t0 = time.time()
    try:
        results = search_top_k(q, top_k, min_score)
        answer = summarize_answer(q, results)
        dt = time.time() - t0
        log_event("ask", request, {"q": q, "top_k": top_k, "min_score": min_score, "count": len(results), "dt_ms": int(dt*1000)})
        return JSONResponse({"ok": True, "query": q, "count": len(results), "results": results, "answer": answer})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== /batch-ask （CSV→CSV）=====
# 入力CSV: ヘッダ行に "query" 列が必要。他列はそのまま返す。
@app.post("/batch-ask")
async def batch_ask(
    request: Request,
    file: UploadFile = File(...),
    query_col: str = Query("query"),
    top_k: int = Query(TOPK_DEFAULT, ge=1, le=50),
    min_score: float = Query(MIN_SCORE_DEFAULT, ge=0.0, le=1.0),
):
    raw = await file.read()
    text = raw.decode("utf-8-sig")  # Excel対策で BOM も許容
    reader = csv.DictReader(io.StringIO(text))
    out_buf = io.StringIO()
    fieldnames = list(reader.fieldnames or [])
    if "answer" not in fieldnames: fieldnames.append("answer")
    if "sources" not in fieldnames: fieldnames.append("sources")
    writer = csv.DictWriter(out_buf, fieldnames=fieldnames)
    writer.writeheader()

    n = 0
    for row in reader:
        q = (row.get(query_col) or "").strip()
        if not q:
            row["answer"] = ""
            row["sources"] = "[]"
            writer.writerow(row); continue
        results = search_top_k(q, top_k, min_score)
        ans = summarize_answer(q, results)
        row["answer"] = ans
        row["sources"] = json.dumps([{"title": r["title"], "score": r["score"], "url": r["source_url"]} for r in results], ensure_ascii=False)
        writer.writerow(row)
        n += 1

    # Excelで開きやすいよう UTF-8-SIG で返す
    out_bytes = ("\ufeff" + out_buf.getvalue()).encode("utf-8")
    log_event("batch-ask", request, {"rows": n})
    headers = {"Content-Disposition": f'attachment; filename="answers.csv"'}
    return StreamingResponse(io.BytesIO(out_bytes), media_type="text/csv; charset=utf-8", headers=headers)
