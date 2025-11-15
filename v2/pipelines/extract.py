# app/extract.py
import requests
import fitz
from bs4 import BeautifulSoup

def extract_from_pdf(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.content

    if not data.startswith(b"%PDF"):
        print(f"[WARN] Not a valid PDF at {url}. content-type={resp.headers.get('content-type')}")
        return ""

    with fitz.open(stream=data, filetype="pdf") as doc:
        texts = [page.get_text() for page in doc]

    return "\n".join(texts)

def extract_from_html(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text(separator="\n")
