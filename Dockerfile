FROM python:3.11-slim

WORKDIR /app

# 軽量・再現性重視
RUN pip install --no-cache-dir fastapi uvicorn

# アプリ配置
COPY ./qa_service.py /app/qa_service.py

# データ置き場
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data/feedback

# ポートは環境変数で（デフォルト 8010）
ENV APP_PORT=8010
ENV VERSION=dev
ENV BUILD_TIME=unknown

CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
