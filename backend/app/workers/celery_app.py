from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "pg_finance",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    # Agendamento (precisa do processo `celery beat` — ver iniciar_celery_beat.bat).
    # DFe: a SEFAZ pede >=1h entre consultas sem documento novo.
    beat_schedule={
        "sincronizar-nfes-sefaz": {"task": "sincronizar_dfe", "schedule": crontab(minute=5)},
        "sincronizar-open-finance": {"task": "sincronizar_open_finance_todas", "schedule": crontab(minute=0, hour="*/4")},
    },
)

from app.workers import tasks  # noqa: E402,F401 — registra as tasks no app acima
