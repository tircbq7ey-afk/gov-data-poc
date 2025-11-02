# export_logs.py  --- logs/qa.log (JSON lines) -> CSV
import argparse, json, csv
from pathlib import Path
from collections import deque

def tail_lines(path: Path, n: int):
    if not path.exists():
        return []
    dq = deque(maxlen=n)
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            dq.append(line.rstrip('\n'))
    return list(dq)

def flatten(obj: dict) -> dict:
    out = {}
    # 共通でよく見るキーを吸い出す（無ければ空）
    for k in [
        "evt","q","top_k","bm25_top_n","w_bm25","w_vec","ip","count",
        "helpful","doc_ids","notes","ts"
    ]:
        v = obj.get(k, "")
        if isinstance(v, (list, tuple)):
            v = ";".join(map(str, v))
        out[k] = v
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", type=int, default=1000)
    ap.add_argument("--out", type=str, default="logs.csv")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent
    log = root / "logs" / "qa.log"
    rows = []
    for line in tail_lines(log, args.lines):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        rows.append(flatten(obj))

    if not rows:
        print("no rows")
        return

    fields = sorted({k for r in rows for k in r.keys()})
    outp = root / args.out
    with outp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote: {outp} rows={len(rows)}")

if __name__ == "__main__":
    main()
