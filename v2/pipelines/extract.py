import logging
from typing import Optional

import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _get_response(url: str) -> requests.Response:
    """共通の HTTP GET。エラー時は例外を投げる。"""
    logger.info("Fetching URL: %s", url)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp


def _extract_from_html_response(resp: requests.Response) -> str:
    """HTMLレスポンスからテキストを抽出する共通処理。"""
    # 文字コードを推定してデコード
    html = resp.content.decode(resp.encoding or "utf-8", errors="ignore")

    soup = BeautifulSoup(html, "html.parser")

    # スクリプトやスタイルは除去
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")

    # 空行や余計な空白を整理
    lines = [line.strip() for line in text.splitlines()]
    chunks = [line for line in lines if line]
    return "\n".join(chunks)


def extract_from_html(url: str) -> str:
    """URL から HTML を取得してテキストを抽出する。"""
    try:
        resp = _get_response(url)
        return _extract_from_html_response(resp)
    except Exception:
        logger.exception("Failed to extract HTML from %s", url)
        return ""


def extract_from_pdf(url: str) -> str:
    """URL から PDF を取得してテキストを抽出する。

    - Content-Type を見て PDF らしくない場合は HTML として処理
    - PyMuPDF でのパースに失敗した場合も HTML として再トライ
    - それでもダメなら空文字を返す（例外で ingest 全体を止めない）
    """
    try:
        resp = _get_response(url)

        content_type = resp.headers.get("Content-Type", "").lower()
        # ヘッダも拡張子も PDF らしくない場合は HTML とみなす
        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            logger.warning(
                "URL does not look like a PDF (Content-Type: %s). "
                "Falling back to HTML extraction: %s",
                content_type,
                url,
            )
            return _extract_from_html_response(resp)

        # いったん PDF としてパースを試す
        try:
            with fitz.open(stream=resp.content, filetype="pdf") as doc:
                texts = [page.get_text("text") for page in doc]
            return "\n".join(texts).strip()
        except Exception as e:
            logger.warning(
                "Failed to parse PDF at %s (%s). Falling back to HTML extraction.",
                url,
                e,
            )
            # 実は HTML が返ってきている可能性が高いので HTML として再トライ
            try:
                return _extract_from_html_response(resp)
            except Exception:
                logger.exception("Fallback HTML extraction also failed for %s", url)
                return ""

    except Exception:
        logger.exception("Failed to fetch or parse PDF from %s", url)
        return ""


def extract_text(url: str, type: Optional[str] = None) -> str:
    """URLとタイプからテキストを抽出するヘルパー。

    ingest 側で type を指定している場合を想定したラッパーです。
    """
    type_lower = (type or "").lower()
    if type_lower == "pdf":
        return extract_from_pdf(url)
    elif type_lower == "html":
        return extract_from_html(url)
    else:
        # よく分からない場合は HTML として扱う
        return extract_from_html(url)
