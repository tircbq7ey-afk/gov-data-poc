import os, json, hashlib, datetime
from app.store.vector import upsert
from pipelines.extract import extract_from_pdf, extract_from_html
DATA_DIR = os.getenv("DATA_DIR","./data")
os.makedirs(DATA_DIR, exist_ok=True)
SEED = "./pipelines/config/seed_urls.json"
def sha(s: str): return hashlib.sha256(s.encode("utf-8")).hexdigest()
def load_seed():
    with open(SEED, "r", encoding="utf-8") as f:
        return json.load(f)
def run():
    seeds = load_seed()
    docs = []
    crawled_at = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    for s in seeds:
        if s["type"]=="pdf":
            text = extract_from_pdf(s["url"])
            title = s.get("title") or "出典"
        else:
            title, text = extract_from_html(s["url"])
        doc_id = sha(s["url"])
        docs.append({
            "id": doc_id,
            "text": text[:10000],
            "meta": {
                "url": s["url"],
                "title": title,
                "published_at": s.get("published_at"),
                "crawled_at": crawled_at,
                "lang": s.get("lang","ja")
            }
        })
    upsert(docs)
    print(f"ingested: {len(docs)}")
if __name__ == "__main__":
    run()
