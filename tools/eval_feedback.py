# tools/eval_feedback.py
import csv, os, datetime as dt
from collections import Counter
import matplotlib.pyplot as plt

LOG = os.getenv("LOG_DIR", "logs")
OUT = "reports"
CHART = os.path.join(OUT, "charts")
os.makedirs(CHART, exist_ok=True)

fb = os.path.join(LOG, "feedback.csv")
if not os.path.exists(fb):
    raise SystemExit(f"feedback.csv がありません: {fb}")

rows = []
with open(fb, encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)

c = Counter([r["label"] for r in rows])
good = c.get("good", 0)
bad  = c.get("needs_improvement", 0)
total = good + bad
good_ratio = (good/total)*100 if total else 0

# サマリ CSV
os.makedirs(OUT, exist_ok=True)
summary_path = os.path.join(OUT, "feedback_summary.csv")
with open(summary_path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "total", "good", "needs_improvement", "good_ratio(%)"])
    today = dt.date.today().isoformat()
    w.writerow([today, total, good, bad, round(good_ratio, 1)])

# 上位の「改善が必要」質問を出す
needs_path = os.path.join(OUT, "needs_improvement_top.csv")
bad_q = Counter([r["q"] for r in rows if r["label"]=="needs_improvement"])
with open(needs_path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(["q","count"])
    for q, n in bad_q.most_common(30):
        w.writerow([q, n])

# 棒グラフ
plt.figure()
plt.bar(["good","needs_improvement"], [good, bad])
plt.title("feedback counts")
plt.tight_layout()
png = os.path.join(CHART, "feedback_counts.png")
plt.savefig(png, dpi=150)
print(f"[OK] summary={summary_path}  needs={needs_path}  chart={png}")
