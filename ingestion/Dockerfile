FROM python:3.12-slim

LABEL org.opencontainers.image.title="Yomi ingestion"
LABEL org.opencontainers.image.description="Content database initialization scaffold for Yomi."

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ingest.py ./ingest.py

CMD ["python", "ingest.py"]
