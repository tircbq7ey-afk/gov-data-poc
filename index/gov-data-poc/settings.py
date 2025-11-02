# -*- coding: utf-8 -*-
import os

# 重要：OpenAI の埋め込みを使う場合は環境変数でキーを設定しておく
# $env:OPENAI_API_KEY="sk-xxxx"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# 埋め込みモデル（コストを抑えるなら小さめでOK）
EMBEDDING_MODEL = "text-embedding-3-small"  # 必要に応じて変更

# パス
DATA_DIR = "data"
RAW_DIR = os.path.join(DATA_DIR, "raw")
PARSED_DIR = os.path.join(DATA_DIR, "parsed")
DB_DIR = os.path.join(DATA_DIR, "db")
META_DIR = os.path.join(DATA_DIR, "meta")

# DBファイル
TEXTS_JSON = os.path.join(DB_DIR, "texts.json")
FAISS_INDEX = os.path.join(DB_DIR, "faiss.index")
ID_MAP_JSON = os.path.join(DB_DIR, "id_map.json")
DOC_MAP_JSON = os.path.join(DB_DIR, "doc_map.json")
MANIFEST_JSON = os.path.join(META_DIR, "manifest.json")

# チャンク関連
CHUNK_SIZE = 900     # 文字めやす（日本語でもOK）
CHUNK_OVERLAP = 150  # 前後つなぎのために少しかぶせる
MAX_DOC_TOKENS = 300000  # 巨大PDFを暴れないように安全弁

# ユーザーエージェント
CRAWLER_UA = "GovDataBot/1.0 (+https://example.com)"
REQUEST_TIMEOUT = 30
