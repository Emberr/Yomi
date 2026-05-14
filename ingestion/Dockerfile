FROM python:3.12-slim

LABEL org.opencontainers.image.title="Yomi ingestion"
LABEL org.opencontainers.image.description="Content database ingestion for Yomi."

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir .

COPY ingest.py ./

CMD ["python", "ingest.py"]
