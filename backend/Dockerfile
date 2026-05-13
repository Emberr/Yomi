FROM python:3.12-slim

LABEL org.opencontainers.image.title="Yomi backend"
LABEL org.opencontainers.image.description="FastAPI backend for Yomi."

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY yomi ./yomi
COPY tests ./tests

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir ".[test]"

EXPOSE 8000

CMD ["uvicorn", "yomi.main:app", "--host", "0.0.0.0", "--port", "8000"]
