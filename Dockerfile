FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 依存（必要なら requirements.txt を使ってもOK）
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# アプリ配置
COPY app /app

# 実行時環境
ENV WEB_ROOT=/app/www
ENV DATA_DIR=/app/data
ENV API_KEY=changeme-local-token

# ディレクトリを用意
RUN mkdir -p /app/www /app/data/feedback /app/data/flags

EXPOSE 8010
CMD ["python", "-m", "uvicorn", "qa_service:APP", "--host", "0.0.0.0", "--port", "8010"]
