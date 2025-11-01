# ./Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 依存最小
RUN pip install --no-cache-dir fastapi uvicorn

# アプリ本体
COPY ./qa_service.py /app/qa_service.py

# ポート
EXPOSE 8010

# 環境変数（ビルド時に上書き可）
ENV VERSION=dev BUILD_TIME=unknown

CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
