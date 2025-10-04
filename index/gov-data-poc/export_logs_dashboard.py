# export_logs_dashboard.py
import json, re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "logs" / "qa.log"
OUT = ROOT / "logs" / "dashboard.html"

def load():
    rows = []
    if not LOG.exists():
        return rows
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            rows.append(obj)
        except Exception:
            # logging prefix only? try to extract json
            m = re.search(r"(\{.*\})", line)
            if m:
                try:
                    rows.append(json.loads(m.group(1)))
                except Exception:
                    pass
    return rows

def main():
    rows = load()
    evt_cnt = Counter([r.get("evt","") for r in rows])
    helpful = [r for r in rows if r.get("evt")=="feedback"]
    good = sum(1 for r in helpful if r.get("helpful") is True)
    bad  = sum(1 for r in helpful if r.get("helpful") is False)
    # top queries
    q_cnt = Counter([r.get("q","") for r in rows if r.get("q")])
    top_q = q_cnt.most_common(20)

    html = f"""<!doctype html><meta charset="utf-8">
<title>QA Dashboard</title>
<style>
body{{font-family:system-ui,Segoe UI,Roboto,Arial;margin:24px;}}
table{{border-collapse:collapse}}
td,th{{border:1px solid #ccc;padding:6px 8px}}
small{{color:#666}}
</style>
<h1>QA Dashboard</h1>
<small>generated at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</small>
<h2>Events</h2>
<table><tr><th>event</th><th>count</th></tr>
{"".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k,v in evt_cnt.items())}
</table>
<h2>Feedback</h2>
<p>👍 {good}　/　👎 {bad}　（Total {good+bad}）</p>
<h2>Top Queries</h2>
<table><tr><th>q</th><th>count</th></tr>
{"".join(f"<tr><td>{q}</td><td>{c}</td></tr>" for q,c in top_q)}
</table>
"""
    OUT.write_text(html, encoding="utf-8")
    print(f"OK: {OUT}")

if __name__ == "__main__":
    main()
