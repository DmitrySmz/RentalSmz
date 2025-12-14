FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY alembic.ini .
COPY app/migrations migrations
COPY scripts scripts

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
ENV PYTHONPATH=/app
