#!/bin/bash
# API + worker + beat no mesmo container: API e worker precisam enxergar o
# mesmo disco (PDFs/extratos enviados), e um volume só se monta num serviço.
# Se qualquer processo morrer o container sai e a Railway reinicia tudo.
set -e

mkdir -p "$STORAGE_DIR"
alembic upgrade head

celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 &
celery -A app.workers.celery_app beat --loglevel=info -s /tmp/celerybeat-schedule &
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*" &

wait -n
exit 1
