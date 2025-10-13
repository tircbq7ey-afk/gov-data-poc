from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import csv, os, json

app = FastAPI(
    title="gov-data-poc",
    version="dev",
    description="Prototype API for document Q&A and feedback collection"
)

DATA_PATH = "./data/answers.csv"
FEEDBACK_PATH = "./data/feedback"

# ======================================================
# Health Check
# ======================================================
@app.get("/health", summary="Health")
def health():
    return {"ok": True, "version": "dev"}


# ======================================================
# Q&Aエンドポイント（簡易検索）
# ======================================================
@app.get("/ask", summary="Ask")
def ask(q: str, top_k: int = 3, min_score: float = 0.2, lang: str = "ja"):
    try:
        if not os.path.exists(DATA_PATH):
            raise HTTPException(status_code=404, detail="Data file not found")

        results = []
        with open(DATA_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if q in row["question"]:
                    results.append(row)

        if not results:
            return {"q": q, "lang": lang, "answer": "該当データが見つかりませんでした。", "sources": []}

        # 仮スコアで上位 top_k 件を返す
        results = results[:top_k]
        return {
            "q": q,
            "lang": lang,
            "answer": [r["answer"] for r in results],
            "sources": [r["source"] for r in results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ======================================================
# Feedback エンドポイント
# ======================================================
class Feedback(BaseModel):
    q: str
    answer: str
    sources: list[str]
    lang: str = "ja"

@app.post("/feedback", summary="Feedback")
def feedback(fb: Feedback):
    os.makedirs(FEEDBACK_PATH, exist_ok=True)
    path = os.path.join(FEEDBACK_PATH, "20251013.jsonl")

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(fb.dict(), ensure_ascii=False) + "\n")

    return {"ok": True, "path": path}


# ======================================================
# 管理者用：CSVデータ再読み込み
# ======================================================
@app.post("/admin/reindex", summary="Rebuild index")
def admin_reindex():
    if not os.path.exists(DATA_PATH):
        raise HTTPException(status_code=404, detail="Data file not found")

    with open(DATA_PATH, encoding="utf-8") as f:
        row_count = sum(1 for _ in csv.DictReader(f))

    return {"ok": True, "docs": row_count}
