# batch_ask.py - ローカルでCSV→回答CSV（APIを叩かず関数直呼びでもOK）
import csv, io, json, sys
from pathlib import Path
from qa_service import search_top_k, summarize_answer, MIN_SCORE_DEFAULT, TOPK_DEFAULT

def run(in_csv: Path, out_csv: Path, query_col="query", top_k=TOPK_DEFAULT, min_score=MIN_SCORE_DEFAULT):
    text = in_csv.read_text("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    out_buf = io.StringIO()
    flds = list(reader.fieldnames or [])
    for col in ("answer", "sources"):
        if col not in flds: flds.append(col)
    w = csv.DictWriter(out_buf, fieldnames=flds)
    w.writeheader()

    n = 0
    for row in reader:
        q = (row.get(query_col) or "").strip()
        if not q:
            row["answer"] = ""; row["sources"] = "[]"
            w.writerow(row); continue
        results = search_top_k(q, top_k, min_score)
        row["answer"] = summarize_answer(q, results)
        row["sources"] = json.dumps([{"title": r["title"], "score": r["score"], "url": r["source_url"]}], ensure_ascii=False)
        w.writerow(row); n += 1

    out_csv.write_bytes(("\ufeff"+out_buf.getvalue()).encode("utf-8"))
    print(f"done: {n} rows -> {out_csv}")

if __name__ == "__main__":
    inp = Path(sys.argv[1]); outp = Path(sys.argv[2]) if len(sys.argv)>2 else Path("answers.csv")
    run(inp, outp)
