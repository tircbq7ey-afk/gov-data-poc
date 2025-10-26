# /Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data

WORKDIR /app

# 依存
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# アプリと Web を配置
COPY qa_service.py /app/qa_service.py
# リポジトリ直下の index.html を配信場所にコピー（無いと 404 になります）
COPY index.html /app/www/index.html

EXPOSE 8010
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
