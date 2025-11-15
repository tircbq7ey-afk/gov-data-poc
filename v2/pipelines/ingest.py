# v2/pipelines/ingest.py
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------- path helpers ----------
HERE = Path(__file__).resolve().parent          # .../v2/pipelines
V2_ROOT = HERE.parent                           # .../v2
REPO_ROOT = V2_ROOT.parent                      # repo root

DEFAULT_SEED = HERE / "config" / "seed_urls.json"

def resolve_path(p: str | Path) -> Path:
    """Windowsでも安全に解決。相対なら
    1) 現在dir, 2) v2/, 3) v2/pipelines/ から探索。"""
    cand: List[Path] = []
    ip = Path(p)
    if ip.is_absolute():
        cand.append(ip)
    else:
        cand += [
            Path.cwd() / ip,
            V2_ROOT / ip,
            HERE / ip,
        ]
    for c in cand:
        if c.exists():
            return c.resolve()
    # 見つからない場合は最初の候補を返す（上でエラー表示）
    return cand[0] if cand else ip

# ---------- robust JSON loader ----------
def load_json_robust(path: Path) -> Any:
    """
    UTF-8 / UTF-8-SIG(BOM) のどちらでも読み込む。
    先頭3バイトが BOM の場合は自動でスキップ。
    """
    # まずはバイナリで読み BOM を判定
    raw = path.read_bytes()
    # UTF-8 BOM
    if raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")
    else:
        # 念のため utf-8 で
        text = raw.decode("utf-8")
    return json.loads(text)

# ---------- ingestion core (best-effort) ----------
def try_import_ingest_deps():
    """
    依存モジュール（スクレイプ & ベクタ格納）が存在する場合のみ使う。
    なくてもエラーにしない（検証しやすくするため）。
    """
    extract = upsert = None
    try:
        # 例: v2/pipelines/extract.py に fetch_and_split がある前提の軽結合
        # あなたの実装に合わせてここだけ名称を変えてください
        from pipelines.extract import fetch_and_split as extract  # type: ignore
    except Exception:
        pass
    try:
        from app.store.vector import upsert  # type: ignore
    except Exception:
        pass
    return extract, upsert

def ingest(seeds: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    seeds を処理。依存が見つからなければバリデーションのみ。
    戻り値: (処理対象件数, upsert実行件数)
    """
    extract, upsert = try_import_ingest_deps()

    processed = 0
    upserted = 0

    for i, s in enumerate(seeds, 1):
        url = s.get("url") or s.get("URL") or s.get("link")
        if not url:
            print(f"[WARN] seed #{i} に url がありません。スキップ")
            continue
        lang = (s.get("lang") or "ja").lower()
        typ = (s.get("type") or "html").lower()
        title = s.get("title") or ""
        meta = {"lang": lang, "type": typ, "title": title}

        processed += 1

        if extract and upsert:
            try:
                docs = extract(url, meta=meta)
                if docs:
                    upsert(docs)
                    upserted += 1
                    print(f"[OK] upsert: {url} ({len(docs)} docs)")
                else:
                    print(f"[OK] 解析は成功・ドキュメント0件: {url}")
            except Exception as e:
                print(f"[ERROR] ingest失敗: {url} :: {e}")
        else:
            # 依存がない場合は dry-run のように表示のみ
            print(f"[DRY] {url}  lang={lang} type={typ} title={title}")

    return processed, upserted

# ---------- CLI ----------
def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="VisaNavi v2: ingest seed urls")
    p.add_argument(
        "--seed",
        default=str(DEFAULT_SEED),
        help="seed json path (UTF-8/UTF-8-SIG対応). 例: pipelines\\config\\seed_urls.json",
    )
    args = p.parse_args(argv)

    seed_path = resolve_path(args.seed)

    if not seed_path.exists():
        # 探索ログを出しておく
        print("[ERROR] seedファイルが見つかりません。探した場所:")
        print(f" - {Path.cwd() / Path(args.seed)}")
        print(f" - {V2_ROOT / Path(args.seed)}")
        print(f" - {HERE / Path(args.seed)}")
        print(f"最後に解決したパス: {seed_path}")
        return 2

    try:
        seeds = load_json_robust(seed_path)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSONの読み込みに失敗しました（BOM含むUTF-8に対応済みだが内容が不正の可能性）。")
        print(f"  ファイル: {seed_path}")
        print(f"  詳細: {e}")
        return 3

    if not isinstance(seeds, list):
        print(f"[ERROR] 期待した形式は配列(list)ですが、{type(seeds)} が読み込まれました。ファイル: {seed_path}")
        return 4

    print(f"[INFO] seeds 読み込み OK: {len(seeds)}件  ({seed_path})")
    processed, upserted = ingest(seeds)
    print(f"[DONE] processed={processed}, upserted={upserted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
