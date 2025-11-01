FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic[dotenv]

# アプリ配置
COPY app ./app
COPY www ./www

# データ用ディレクトリ（初回から存在させる）
RUN mkdir -p /app/data/feedback /app/data/flags
