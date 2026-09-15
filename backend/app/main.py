from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import (
    assistente,
    auditoria,
    auth,
    categorias_lancamento,
    centros_custo,
    conciliacoes,
    contas_bancarias,
    contas_financeiras,
    extratos,
    indicadores,
    lancamentos_recorrentes,
    notas_fiscais,
    parceiros,
    pre_lancamentos_whatsapp,
    sistema,
    usuarios,
    whatsapp_webhook,
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
app.include_router(usuarios.router)
app.include_router(parceiros.router)
app.include_router(centros_custo.router)
app.include_router(categorias_lancamento.router)
app.include_router(contas_bancarias.router)
app.include_router(lancamentos_recorrentes.router)
app.include_router(contas_financeiras.router)
app.include_router(notas_fiscais.router)
app.include_router(extratos.router)
app.include_router(conciliacoes.router)
app.include_router(assistente.router)
app.include_router(indicadores.router)
app.include_router(pre_lancamentos_whatsapp.router)
app.include_router(whatsapp_webhook.router)
app.include_router(auditoria.router)
app.include_router(sistema.router)

Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.storage_dir), name="storage")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
