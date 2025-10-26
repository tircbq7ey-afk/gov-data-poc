# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# ランタイムに必要な最小限
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

# 依存（今回は最小）
RUN pip install --no-cache-dir fastapi uvicorn

# アプリ
COPY ./app/qa_service.py /app/qa_service.py

# 静的ファイル（/app/www）— ルートに index.html を置いている場合はここへコピー
# 例: リポジトリ直下の index.html を app/www/index.html として取り込む
COPY ./app/www /app/www
# 上行で何もコピーされない場合に備えて空ディレクトリだけ用意
RUN mkdir -p /app/www

EXPOSE 8010

# uvicorn 起動
CMD ["uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010", "--proxy-headers"]
