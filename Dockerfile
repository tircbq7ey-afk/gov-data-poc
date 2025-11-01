# Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 必要ライブラリ
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# 作業ディレクトリ
WORKDIR /app

# アプリと静的ファイルをコピー（www は volume で差し替え予定でもOK）
COPY app ./app
COPY www ./www

# データディレクトリ（volumeで上書き）
RUN mkdir -p /app/data

ENV APP_PORT=8010 \
    WEB_ROOT=/app/www \
    DATA_DIR=/app/data \
    API_TOKEN=changeme-local-token

EXPOSE 8010
CMD ["python", "-m", "uvicorn", "app.qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
