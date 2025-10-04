import argparse, csv
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

p = argparse.ArgumentParser()
p.add_argument("-i", "--input_dir", required=True)
p.add_argument("-o", "--out_dir", required=True)
args = p.parse_args()

inp = Path(args.input_dir)
out = Path(args.out_dir)
out.mkdir(parents=True, exist_ok=True)

fb = inp / "feedback.csv"
if not fb.exists():
    print("feedback.csv が見つかりません。終了します。")
    raise SystemExit(0)

cnt = Counter()
with fb.open(encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cnt[row.get("label","unknown")] += 1

# 単純な棒グラフ
labels = list(cnt.keys())
values = [cnt[k] for k in labels]

plt.figure()
plt.bar(labels, values)
plt.title("feedback counts")
plt.tight_layout()
out_png = out / "feedback_counts.png"
plt.savefig(out_png)
print(f"saved: {out_png}")
