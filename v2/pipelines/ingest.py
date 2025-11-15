import argparse
import datetime
import json
import logging
from pathlib import Path

import requests
import fitz  # PyMuPDF


logger = logging.getLogger(__name__)


def load_seed(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_from_pdf(url: str) -> str:
    """
    PDF をテキスト化する。
    PDF として開けなかった場合は例外をキャッチして
    単純にレスポンスボディを文字列として返す。
    """
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    try:
        with fitz.open(stream=resp.content, filetype="pdf") as doc:
            texts = [page.get_text("text") for page in doc]
        text = "\n".join(texts).strip()
        if not text:
            logger.warning("PDF からテキストが抽出できませんでした: %s", url)
            text = resp.text
        return text
    except Exception as e:
        logger.warning(
            "PDF としての解析に失敗したため、HTMLテキストとして扱います: %s (%s)",
            url,
            e,
        )
        return resp.text


def extract_from_html(url: str) -> str:
    """
    HTML ページのテキスト抽出。
    ひとまずはプレーンテキストとして全文を持っておく。
    """
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def run(seed_path: str) -> None:
    seeds = load_seed(seed_path)

    out_path = Path("data") / "docs.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    crawled_at = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    with out_path.open("w", encoding="utf-8") as f:
        for s in seeds:
            url = s["url"]
            doc_type = s.get("type", "html")

            if doc_type == "pdf":
                text = extract_from_pdf(url)
            else:
                text = extract_from_html(url)

            record = {
                "url": url,
                "type": doc_type,
                "lang": s.get("lang", "ja"),
                "title": s.get("title", ""),
                "published_at": s.get("published_at") or "",
                "crawled_at": crawled_at,
                "text": text,
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.info("ingested: %s", url)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        default="pipelines/config/seed_urls.json",
        help="シードURLを定義したJSONのパス",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    run(args.seed)


if __name__ == "__main__":
    main()
