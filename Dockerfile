FROM python:3.11-slim

WORKDIR /app
COPY ./app/qa_service.py /app/qa_service.py

RUN pip install --no-cache-dir fastapi uvicorn pydantic

EXPOSE 8010
CMD ["python", "-m", "uvicorn", "qa_service:app", "--host", "0.0.0.0", "--port", "8010"]
