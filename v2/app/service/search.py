# app/service/search.py
from typing import Any, Dict, List

from fastapi import HTTPException

from app.store.vector import get_vector_store


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    /search エンドポイントから呼ばれるハンドラ。
    payload は {"query": "...", "k": 5} 形式の dict を想定。
    """
    if "query" not in payload:
        raise HTTPException(status_code=400, detail="field 'query' is required")

    query = str(payload["query"])
    k = int(payload.get("k", 5))

    collection = get_vector_store()

    try:
        result = collection.query(
            query_texts=[query],
            n_results=k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")

    ids = result.get("ids", [[]])[0]
    distances = result.get("distances", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    documents = result.get("documents", [[]])[0]

    hits: List[Dict[str, Any]] = []
    for i, doc_id in enumerate(ids):
        hits.append(
            {
                "id": doc_id,
                "score": distances[i] if i < len(distances) else None,
                "metadata": metadatas[i] if i < len(metadatas) else None,
                "document": documents[i] if i < len(documents) else None,
            }
        )

    return {"results": hits}
