import os, json
from datetime import datetime
from ..models.schema import FeedbackRequest
FEEDBACK_DIR = os.getenv("FEEDBACK_DIR", "./data/feedback")
os.makedirs(FEEDBACK_DIR, exist_ok=True)
def save(req: FeedbackRequest):
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(FEEDBACK_DIR, f"{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(req.model_dump(), f, ensure_ascii=False, indent=2)
    return {"ok": True}
