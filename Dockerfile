# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# ランタイムのみ最小限
RUN pip install --no-cache-dir fastapi uvicorn

# アプリ本体
COPY ./app/qa_service.py /app/qa_service.py

# データ用のマウントポイント
RUN mkdir -p /app/data/feedback /app/data/flags

EXPOSE 8010
CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
