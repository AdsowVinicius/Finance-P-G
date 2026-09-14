@echo off
cd /d "C:\dev\PG finance\backend"
".venv\Scripts\celery.exe" -A app.workers.celery_app worker --loglevel=info --pool=solo
