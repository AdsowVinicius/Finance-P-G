# Backend (API + Celery worker + beat num container só) — deploy na Railway.
# Contexto = raiz do repo porque a migration 0001 lê ../schema.sql.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY schema.sql schema.sql
COPY backend backend
# o checkout no Windows pode trazer CRLF, que quebra o shebang/sh
RUN sed -i 's/\r$//' backend/docker-entrypoint.sh && chmod +x backend/docker-entrypoint.sh

WORKDIR /srv/backend
ENV STORAGE_DIR=/data/storage
CMD ["./docker-entrypoint.sh"]
