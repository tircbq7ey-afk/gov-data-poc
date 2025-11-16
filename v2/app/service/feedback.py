# app/service/feedback.py

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

try:
    # pydantic v2 想定
    from app.models.schema import FeedbackRequest
except ImportError:
    # 万一 import できない場合でもタイプヒントなしで動くようにしておく
    FeedbackRequest = Any  # type: ignore


# フィードバック保存先ディレクトリ
DATA_DIR = Path(os.getenv("DATA_DIR", "data")).resolve()
FEEDBACK_DIR = DATA_DIR / "feedback"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def _model_to_dict(obj: Any) -> Dict[str, Any]:
    """Pydantic v1/v2 の違いを吸収して dict に変換するユーティリティ."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    # 最悪、__dict__ を使う
    return dict(obj.__dict__)


def handle(request: FeedbackRequest) -> Dict[str, Any]:
    """
    /feedback エンドポイントから呼ばれるハンドラ.

    受け取ったフィードバックを data/feedback/ 配下に
    JSON ファイルとして保存し、ステータスを返すだけの
    シンプルな実装にしています。
    """
    payload = _model_to_dict(request)

    # タイムスタンプ付きのファイル名を作成
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out_file = FEEDBACK_DIR / f"feedback_{ts}.json"

    with out_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return {"status": "ok"}
