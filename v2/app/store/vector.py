import os
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# ベクトルDBの保存先ディレクトリ
DATA_DIR = Path(os.getenv("DATA_DIR", "data")).resolve()
VECTOR_DIR = DATA_DIR / "chroma"

VECTOR_DIR.mkdir(parents=True, exist_ok=True)

# OpenAI の埋め込み関数
# ※ OPENAI_API_KEY は .env などで設定してある前提
_embedding_fn = OpenAIEmbeddingFunction(
    model_name="text-embedding-3-small",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

# Chroma のクライアント & コレクションを初期化
_client = chromadb.PersistentClient(path=str(VECTOR_DIR))

_collection = _client.get_or_create_collection(
    name="gov-docs",
    embedding_function=_embedding_fn,
)


def get_vector_store():
    """
    FastAPI 側などからコレクションを取得するための関数
    """
    return _collection


def upsert(documents: List[Dict[str, Any]]) -> None:
    """
    ingest パイプラインから呼ばれる想定の upsert 関数。

    documents の想定フォーマット:
        [
            {
                "id": str,
                "text": str,
                "metadata": dict(任意)
            },
            ...
        ]
    """
    if not documents:
        return

    ids = [str(d["id"]) for d in documents]
    texts = [d["text"] for d in documents]
    metadatas = [d.get("metadata") or {} for d in documents]

    _collection.upsert(
        ids=ids,
        documents=texts,
        metadatas=metadatas,
    )


def query(query_text: str, k: int = 5) -> Dict[str, Any]:
    """
    検索用のユーティリティ関数。
    service/search.py などから呼ばれる想定。

    :param query_text: ユーザーの質問文
    :param k: 取得する件数
    """
    return _collection.query(
        query_texts=[query_text],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
