# Dockerfile
FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn

COPY ./qa_service.py /app/qa_service.py

ENV APP_PORT=8010
EXPOSE 8010

CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
