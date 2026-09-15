from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import (
    assistente,
    auth,
    centros_custo,
    contas_bancarias,
    contas_financeiras,
    extratos,
    lancamentos_recorrentes,
    notas_fiscais,
    parceiros,
)

app = FastAPI(title="Finance P&G", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(parceiros.router)
app.include_router(centros_custo.router)
app.include_router(contas_bancarias.router)
app.include_router(lancamentos_recorrentes.router)
app.include_router(contas_financeiras.router)
app.include_router(notas_fiscais.router)
app.include_router(extratos.router)
app.include_router(assistente.router)

Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.storage_dir), name="storage")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
