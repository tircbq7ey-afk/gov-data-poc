# -*- coding: utf-8 -*-
from typing import List
from ..models.schema import SearchRequest, SearchResponse, Citation
from ..store import vector

def handle(req: SearchRequest) -> SearchResponse:
    docs, metas = vector.search(req.query, k=req.k or 5)

    cits: List[Citation] = []
    for i, m in enumerate(metas):
        if not m:
            continue
        cits.append(
            Citation(
                url=m.get("url", ""),
                title=m.get("title", ""),
                chunk_index=m.get("chunk_index", i),
            )
        )

    answer = "ok" if docs else "no hits"
    return SearchResponse(answer=answer, citations=cits, score=1.0 if docs else 0.0)
