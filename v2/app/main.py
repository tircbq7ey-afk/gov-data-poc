import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# 検索ロジック本体
from app.service.search import handle as search_handle

# --------------------------------------------------------------------
# 設定
# --------------------------------------------------------------------
APP_PORT = int(os.getenv("APP_PORT", "8000"))
WEB_ROOT = Path(os.getenv("WEB_ROOT", "./www")).resolve()
DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"

# ディレクトリ作成
for p in (WEB_ROOT, DATA_DIR, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------
# FastAPI アプリ本体
# --------------------------------------------------------------------
APP = FastAPI(title="gov-data-poc v2")

APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静的ファイル（フロントエンド）があればマウント
if WEB_ROOT.exists():
    APP.mount("/static", StaticFiles(directory=str(WEB_ROOT)), name="static")


# --------------------------------------------------------------------
# ヘルスチェック
# --------------------------------------------------------------------
@APP.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# --------------------------------------------------------------------
# 検索エンドポイント
#   - なるべく「なんでも受け取れる」ようにして、
#     中で安全に query / k を取り出して search_handle に渡します
# --------------------------------------------------------------------
@APP.post("/search")
def search(payload: Any = Body(...)) -> JSONResponse:
    """
    期待する JSON:
        { "query": "在留カード 住所 変更", "k": 5 }
    """

    # まず JSON ボディを dict として扱えるようにする
    if isinstance(payload, dict):
        body = payload
    else:
        # dict 以外はエラー
        raise HTTPException(
            status_code=400,
            detail="invalid request body: expected JSON object",
        )

    query = body.get("query")
    k = body.get("k", 5)

    if not isinstance(k, int):
        try:
            k = int(k)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="invalid 'k': must be an integer",
            )

    if not query:
        # ここが今出ているエラー箇所だったので、メッセージはそのまま残します
        raise HTTPException(
            status_code=400,
            detail="field 'query' is required",
        )

    try:
        # search_handle の実装に合わせて2パターン試す
        # 1) handle(query, k)
        try:
            results = search_handle(query, k)
        except TypeError:
            # 2) handle({"query": ..., "k": ...})
            results = search_handle({"query": query, "k": k})
    except HTTPException:
        raise
    except Exception as e:
        # ここで例外を握りつぶして 500 として返す
        raise HTTPException(
            status_code=500,
            detail=f"search failed: {e}",
        )

    return JSONResponse({"results": results})


# --------------------------------------------------------------------
# フィードバック保存（必要なら）
# --------------------------------------------------------------------
@APP.post("/feedback")
def feedback(item: Dict[str, Any] = Body(...)) -> Dict[str, str]:
    """
    何かフィードバック JSON を投げると data/feedback 以下に保存するだけの簡易実装
    """
    try:
        # 適当なファイル名
        path = FEEDBACK_DIR / "feedback.jsonl"
        line = (str(item) + "\n").encode("utf-8")
        with open(path, "ab") as f:
            f.write(line)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to save feedback: {e}")
    return {"status": "ok"}


# --------------------------------------------------------------------
# フラグ保存（必要なら）
# --------------------------------------------------------------------
@APP.post("/flag")
def flag(item: Dict[str, Any] = Body(...)) -> Dict[str, str]:
    try:
        path = FLAGS_DIR / "flags.jsonl"
        line = (str(item) + "\n").encode("utf-8")
        with open(path, "ab") as f:
            f.write(line)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to save flag: {e}")
    return {"status": "ok"}


# --------------------------------------------------------------------
# ルート（index.html があればそれを返す）
# --------------------------------------------------------------------
@APP.get("/")
def root():
    index_html = WEB_ROOT / "index.html"
    if index_html.exists():
        return FileResponse(str(index_html))
    return {"message": "gov-data-poc v2 backend running"}
