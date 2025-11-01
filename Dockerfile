FROM python:3.11-slim

WORKDIR /app

# 依存関係
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY app/qa_service.py app/qa_service.py

ENV APP_PORT=8010
CMD ["python", "-m", "uvicorn", "app.qa_service:app", "--host", "0.0.0.0", "--port", "8010", "--proxy-headers", "--forwarded-allow-ips", "*"]
