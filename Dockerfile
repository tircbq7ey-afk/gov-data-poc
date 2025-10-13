# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Python設定（キャッシュやバッファ無効化）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 作業ディレクトリ
WORKDIR /app

# ヘルスチェック用 curl だけインストール（軽量）
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# FastAPI + Uvicorn のみ最小構成でインストール
RUN pip install --no-cache-dir fastapi uvicorn

# 🔹 appフォルダ全体をコピー（qa_service.py 含む）
COPY ./app /app

# 🔹 データフォルダもコピー（CSVなど）
COPY ./data /app/data

# ポート指定（Uvicorn で使用）
EXPOSE 8010

# コンテナのヘルスチェック（FastAPI /health エンドポイント）
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8010/health || exit 1

# アプリ実行コマンド
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
