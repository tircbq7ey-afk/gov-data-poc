# query.py (complete)
# 機能:
# - data/db/faiss.index と data/db/texts.json を読み込み、類似検索
# - --k, --threshold, --json, --model などの引数に対応
# - 何も渡さなければ対話モードで検索
# - 各種安全/整合チェックと分かりやすいエラーメッセージ

from __future__ import annotations
import argparse, json, sys, pathlib, textwrap, os
from typing import List, Dict, Any

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# ==== 既定パス/モデル ====
DB_DIR      = pathlib.Path("data/db")
INDEX_PATH  = DB_DIR / "faiss.index"
META_PATH   = DB_DIR / "texts.json"
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# ==== 端末装飾 ====
def _color(s: str, code: str) -> str:
    if not sys.stdout.isatty():
        return s
    return f"\033[{code}m{s}\033[0m"

BOLD  = lambda s: _color(s, "1")
DIM   = lambda s: _color(s, "2")
GREEN = lambda s: _color(s, "32")
YEL   = lambda s: _color(s, "33")
CYAN  = lambda s: _color(s, "36")

# ==== ユーティリティ ====
def die(msg: str, hint: str | None = None, code: int = 1) -> None:
    print(_color("ERROR: ", "31") + msg, file=sys.stderr)
    if hint:
        print(DIM("hint: " + hint), file=sys.stderr)
    sys.exit(code)

def load_index_and_meta() -> tuple[faiss.Index, List[Dict[str, Any]]]:
    if not INDEX_PATH.exists():
        die(f"FAISS index が見つかりません: {INDEX_PATH}",
            hint="embed.py を実行してベクトルDBを作成してください。")

    if not META_PATH.exists():
        die(f"メタデータが見つかりません: {META_PATH}",
            hint="parse.py → embed.py の順で処理をやり直してください。")

    try:
        index = faiss.read_index(str(INDEX_PATH))
    except Exception as e:
        die(f"faiss.index の読込に失敗しました: {e}",
            hint="ファイル破損の可能性。embed を再実行して再生成してください。")

    try:
        meta_root = json.loads(META_PATH.read_text(encoding="utf-8"))
        meta = meta_root["meta"]
    except Exception as e:
        die(f"texts.json の読込に失敗しました: {e}",
            hint="JSON 形式や 'meta' 配列をご確認ください。")

    # 整合チェック: faiss のベクトル数と meta 件数
    try:
        ntotal = index.ntotal
    except Exception:
        ntotal = None
    if ntotal is not None and ntotal != len(meta):
        die(f"ベクトル数({ntotal})とメタ件数({len(meta)})が一致しません。",
            hint="parse の出力→embed をやり直して同期を取ってください。")

    return index, meta

def make_model(name: str) -> SentenceTransformer:
    try:
        # CPU想定（GPUを使うなら device='cuda' を付ける）
        return SentenceTransformer(name)
    except Exception as e:
        die(f"埋め込みモデルのロードに失敗: {e}",
            hint=f"--model で別モデルを指定するか、ネットワーク/権限をご確認ください。")

def encode_queries(model: SentenceTransformer, queries: List[str]) -> np.ndarray:
    vec = model.encode(queries, normalize_embeddings=True)
    # faiss 用に float32 へ
    if vec.dtype != np.float32:
        vec = vec.astype("float32")
    return vec

def search(index: faiss.Index, meta: List[Dict[str, Any]],
           model: SentenceTransformer, query: str, k: int, threshold: float
           ) -> List[Dict[str, Any]]:
    qv = encode_queries(model, [query])
    scores, ids = index.search(qv, k)
    ids = ids[0]
    scores = scores[0]

    results: List[Dict[str, Any]] = []
    for rank, (i, sc) in enumerate(zip(ids, scores), 1):
        if i < 0:
            continue  # 該当なし
        # cosine 類似度（normalize_embeddings=True で内積=cos類似度）
        score = float(sc)
        if score < threshold:
            continue

        m = meta[int(i)]
        # texts.json 側の代表フィールド名に合わせて安全に取得
        title   = m.get("title") or m.get("id") or "(no title)"
        source  = m.get("source") or m.get("source_url") or m.get("source_path") or ""
        preview = (m.get("preview") or m.get("text", "")[:160]).replace("\n", " ")
        results.append({
            "rank": rank,
            "score": round(score, 4),
            "title": title,
            "source": source,
            "preview": preview,
            **{k: v for k, v in m.items() if k not in {"title","source","preview"}}
        })
    return results

# ==== CLI ====
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="query.py",
        description="FAISS + Sentence-Transformers による日本語/多言語の意味検索"
    )
    p.add_argument("query", nargs="*", help="検索クエリ（未指定なら対話モード）")
    p.add_argument("-k", "--top-k", type=int, default=5, help="上位何件を取得するか（既定: 5）")
    p.add_argument("-t", "--threshold", type=float, default=-1.0,
                   help="スコア閾値（cos類似度、-1〜1。例: 0.3）")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"SentenceTransformer のモデル名（既定: {DEFAULT_MODEL}）")
    p.add_argument("--json", action="store_true", help="結果を JSON で出力")
    p.add_argument("--no-color", action="store_true", help="色付き出力を無効化（CI等）")
    return p

def main(argv: List[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    args = build_parser().parse_args(argv)

    # カラー無効
    if args.no_color:
        global BOLD, DIM, GREEN, YEL, CYAN
        BOLD = DIM = GREEN = YEL = CYAN = (lambda s: s)

    # データ読み込み
    index, meta = load_index_and_meta()
    model = make_model(args.model)

    def run_once(q: str) -> None:
        res = search(index, meta, model, q, k=args.top_k,
                     threshold=args.threshold if args.threshold is not None else -1.0)
        if args.json:
            print(json.dumps({"query": q, "results": res}, ensure_ascii=False, indent=2))
            return

        if not res:
            print(YEL("No results."), DIM("(一致が見つかりませんでした)"))
            return

        for r in res:
            print(BOLD(f"[{r['rank']}]"), CYAN(f"score={r['score']}"), "-", r["title"])
            if r.get("preview"):
                wrapped = textwrap.fill(r["preview"], width=100, max_lines=2, placeholder=" …")
                print("   ", wrapped)
            if r.get("source"):
                print("    ", DIM(f"source: {r['source']}"))
            print()

    if args.query:
        run_once(" ".join(args.query))
        return 0

    # 対話モード
    print(GREEN("Interactive mode. 空行で終了。"))
    while True:
        try:
            q = input(BOLD("query> ")).strip()
        except EOFError:
            break
        if not q:
            break
        run_once(q)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
