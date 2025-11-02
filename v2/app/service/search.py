from ..store.vector import search as vsearch
from ..models.schema import SearchRequest, SearchResponse, Citation
def build_answer(query: str, hits):
    if not hits:
        return (
            "該当する公的な根拠が見つかりませんでした。/feedback から通報してください。",
            [], 0.0
        )
citations = []
    for h in hits:
        m = h["meta"]
        citations.append(Citation(
            url=m.get("url"),
            title=m.get("title", "出典"),
            published_at=m.get("published_at"),
            crawled_at=m.get("crawled_at")
        ))
    body = [
        "【要約】該当する手続きの根拠資料を確認しました。",
        "【必要書類】出典記載の提出書類を参照してください。",
        "【手順】出典の申請手順の章（または申請様式記載）に従ってください。",
        "【注意】最新情報は出典の日付を必ず確認してください。不明点は所管窓口へ。",
        "【出典】以下にURL・発行日・巡回日を列記します。"
    ]
    ans = "\n".join(body)
    score = 1.0 - min(hits[0].get("score", 0.0), 1.0)
    return ans, citations, score
def handle(req: SearchRequest) -> SearchResponse:
    hits = vsearch(req.query, k=5)
    ans, citations, score = build_answer(req.query, hits)
    return SearchResponse(answer=ans, citations=citations, score=score)
