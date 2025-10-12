# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 基本ツール（curlはhealthcheckとデバッグ用）
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 依存（最小構成）
RUN pip install --no-cache-dir fastapi uvicorn

# アプリ本体
COPY ./app/qa_service.py /app/qa_service.py

EXPOSE 8010

# コンテナ内部のヘルスチェック
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8010/health || exit 1

CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010", "--proxy-headers"]
