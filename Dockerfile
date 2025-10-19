# ベース
FROM python:3.11-slim

# システム基本
RUN apt-get update -y && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# 依存ライブラリ
RUN pip install --no-cache-dir fastapi uvicorn

# アプリコード
COPY ./app/qa_service.py /app/qa_service.py

# ポート（uvicorn）
EXPOSE 8010

# 起動
CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
