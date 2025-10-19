FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# healthcheck 等で使うので curl も入れる
RUN apt-get update -y && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# 依存
RUN pip install --no-cache-dir fastapi uvicorn pydantic

# アプリ配置
COPY ./app/qa_service.py /app/qa_service.py

# データ永続化用ディレクトリ（ボリュームで上書きされるが一応用意）
RUN mkdir -p /app/data/feedback /app/data/flags

# 8010 で待受（nginx からプロキシする）
EXPOSE 8010

# 実行
CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010", "--proxy-headers"]
