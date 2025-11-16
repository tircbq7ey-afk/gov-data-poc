# app/store/vector.py
import os
from pathlib import Path
from typing import Any, Mapping, List
from typing import Optional

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# ベクトルDBの保存先
DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
CHROMA_DIR = DATA_DIR / "chroma"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")

# OpenAI の埋め込み関数
_embedding_fn = OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name="text-embedding-3-small",
)

_client: Optional["chromadb.Client"] = None
_collection: chromadb.Collection | None = None


def _get_client() -> chromadb.Client:
    """Chroma クライアントをシングルトンで返す"""
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(is_persistent=True),
        )
    return _client


def get_vector_store() -> chromadb.Collection:
    """検索・アップサート共通で使うコレクションを返す"""
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name="gov-docs",
            embedding_function=_embedding_fn,
        )
    return _collection


def upsert(
    documents: List[str],
    metadatas: List[Mapping[str, Any]],
    ids: List[str],
) -> None:
    """パイプラインから呼び出すアップサート"""
    collection = get_vector_store()
    collection.upsert(
        documents=list(documents),
        metadatas=list(metadatas),
        ids=list(ids),
    )
