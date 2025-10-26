# app/Dockerfile という想定
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data

WORKDIR /app

# 依存
# requirements.txt がない場合は最低限を直接入れる
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt || \
    pip install --no-cache-dir fastapi uvicorn[standard]

# 必要ディレクトリ
RUN mkdir -p /app/www /app/data/flags /app/data/feedback

# アプリ本体
COPY qa_service.py /app/qa_service.py

# Web ルート（index.html を含むディレクトリ）
# 例: リポジトリの app/www に index.html がある前提
COPY www /app/www

EXPOSE 8010
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
