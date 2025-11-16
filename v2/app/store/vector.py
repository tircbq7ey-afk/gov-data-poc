# app/store/vector.py
import os
import logging
from pathlib import Path
from typing import Any, Dict, List

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

logger = logging.getLogger(__name__)

# =============================
# 設定
# =============================
DATA_DIR = Path(os.getenv("DATA_DIR", "data")).resolve()
VECTOR_DIR = DATA_DIR / "vector_store"
VECTOR_DIR.mkdir(parents=True, exist_ok=True)

COLLECTION_NAME = os.getenv("VECTOR_COLLECTION_NAME", "gov-docs")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY が設定されていません。埋め込み生成時にエラーになります。")

# =============================
# Chroma クライアント初期化
# =============================
_client = chromadb.PersistentClient(path=str(VECTOR_DIR))

_embedding_fn = OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=EMBEDDING_MODEL,
)

_collection = _client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=_embedding_fn,
)


# =============================
# 外部から使う API
# =============================

def get_vector_store():
    """
    search.py から利用するためのハンドルを返す。
    戻り値は Chroma の Collection オブジェクトで、
    .query(...) や .upsert(...) をそのまま呼び出せる。
    """
    return _collection


def _build_id(doc: Dict[str, Any], index: int) -> str:
    """
    ドキュメントの一意な ID を決める.
    ingest から渡される dict を想定しているので、
    id / url / title などがあればそれを利用し、
    なければ index で代用する。
    """
    if "id" in doc and doc["id"]:
        return str(doc["id"])
    if "url" in doc and doc["url"]:
        return str(doc["url"])
    if "title" in doc and doc["title"]:
        return str(doc["title"]) + f"#{index}"
    return f"doc#{index}"


def upsert_documents(documents: List[Dict[str, Any]]) -> None:
    """
    pipelines/ingest.py から呼ばれる想定の関数。
    documents: 各要素は少なくとも "content" キーを持つ dict を想定。
    """
    if not documents:
        logger.info("upsert_documents: ドキュメントが 0 件のため何もしません。")
        return

    ids: List[str] = []
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for idx, doc in enumerate(documents):
        # content が無い場合は空文字にしておく（エラー防止）
        text = str(doc.get("content", ""))
        ids.append(_build_id(doc, idx))
        texts.append(text)

        # content 以外はメタデータとして保存
        meta = {k: v for k, v in doc.items() if k != "content"}
        metadatas.append(meta)

    logger.info("upsert_documents: %d 件をベクターストアに upsert", len(ids))

    _collection.upsert(
        ids=ids,
        documents=texts,
        metadatas=metadatas,
    )
