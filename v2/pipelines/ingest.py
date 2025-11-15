import argparse
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .extract import extract_from_pdf, extract_from_html

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SEED_PATH = ROOT_DIR / "pipelines" / "config" / "seed_urls.json"
STORE_DIR = ROOT_DIR / "store"
STORE_DIR.mkdir(parents=True, exist_ok=True)
DOC_PATH = STORE_DIR / "documents.jsonl"


def load_seed(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """シードURL(JSON)を読み込む。UTF-8 / UTF-8 BOM 両対応。"""
    seed_file = Path(path) if path else DEFAULT_SEED_PATH
    logger.info("Loading seeds from %s", seed_file)

    # UTF-8 / UTF-8-SIG どちらでも読めるようにする
    for enc in ("utf-8-sig", "utf-8"):
        try:
            with seed_file.open("r", encoding=enc) as f:
                data = json.load(f)
            logger.info("Loaded %d seeds using encoding=%s", len(data), enc)
            return data
        except UnicodeError:
            continue

    raise RuntimeError(f"Failed to read seed file as UTF-8: {seed_file}")


def append_doc(doc: Dict[str, Any]) -> None:
    """1 ドキュメントを JSONL に追記保存する。"""
    with DOC_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")


def run(seeds_path: Optional[str] = None) -> None:
    seeds = load_seed(seeds_path)

    for idx, s in enumerate(seeds, start=1):
        url = s.get("url")
        doc_type = s.get("type")
        lang = s.get("lang", "ja")
        title = s.get("title", url)

        logger.info("[%d/%d] processing %s (%s)", idx, len(seeds), url, doc_type)

        try:
            if doc_type == "pdf":
                try:
                    text = extract_from_pdf(url)
                except Exception as e:
                    logger.error("PDF extract failed for %s: %s", url, e)
                    # 壊れたPDFはスキップ
                    continue
            elif doc_type == "html":
                try:
                    text = extract_from_html(url)
                except Exception as e:
                    logger.error("HTML extract failed for %s: %s", url, e)
                    continue
            else:
                logger.warning("Unknown type '%s' for %s, skip", doc_type, url)
                continue

            if not text:
                logger.warning("Empty text extracted from %s, skip", url)
                continue

            crawled_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            doc = {
                "url": url,
                "lang": lang,
                "title": title,
                "text": text,
                "crawled_at": crawled_at,
            }
            append_doc(doc)
            logger.info("Saved document for %s", url)

        except Exception as e:
            logger.exception("Unexpected error while processing %s: %s", url, e)

    logger.info("Ingest finished. Output: %s", DOC_PATH)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        type=str,
        default=None,
        help="Path to seed_urls.json (optional).",
    )
    args = parser.parse_args()
    run(args.seed)
