from fastapi import FastAPI, Body
from datetime import datetime, timezone
from pathlib import Path
import json

app = FastAPI(title="gov-data-poc", version="dev")

DATA_DIR = Path("/app/data")
FEEDBACK_DIR = DATA_DIR / "feedback"
FLAGS_DIR = DATA_DIR / "flags"
for p in (DATA_DIR, FEEDBACK_DIR, FLAGS_DIR):
    p.mkdir(parents=True, exist_ok=True)

@app.post("/feedback")
def feedback(payload: dict):
    out = FEEDBACK_DIR / f"{datetime.now().strftime('%Y%m%d')}.jsonl"
    payload = dict(payload)
    payload["ts"] = datetime.now(timezone.utc).isoformat()
    out.write_text("", encoding="utf-8") if not out.exists() else None
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return {"ok": True, "path": f"./data/feedback/{out.name}"}

@app.post("/admin/reindex")
def admin_reindex(force: bool = Body(False)):
    flag = FLAGS_DIR / "reindexed_at.txt"
    flag.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    return {"ok": True, "forced": bool(force), "flag": str(flag)}
