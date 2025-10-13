# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ヘルスチェック用の curl だけ入れる（軽量）
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# 依存（最小）
RUN pip install --no-cache-dir fastapi uvicorn

# アプリ本体
COPY ./app/qa_service.py /app/qa_service.py
COPY ./data /app/data

# 8010 を使う
EXPOSE 8010

# コンテナ内のヘルスチェック（FastAPI の /health）
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8010/health || exit 1

# 🔴 これが無いとアプリが起動しません
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
