from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.enums import TipoOperacaoNota
from app.schemas.indicador import (
    ItemCentroCusto,
    ItemGastoPrevistoDia,
    ItemStatusNota,
    PontoEvolucaoMensal,
    ResumoIndicadores,
)
from app.services import indicadores_service

router = APIRouter(prefix="/indicadores", tags=["indicadores"], dependencies=[Depends(get_current_user)])


def _mes_referencia(mes: str | None) -> date | None:
    """Converte 'YYYY-MM' (query param) pro primeiro dia daquele mês. None
    quando não informado — cada service function usa o mês atual como padrão.
    """
    if not mes:
        return None
    ano_str, mes_str = mes.split("-")
    return date(int(ano_str), int(mes_str), 1)


@router.get("/resumo", response_model=ResumoIndicadores)
def resumo(mes: str | None = None, db: Session = Depends(get_db)) -> dict:
    return indicadores_service.resumo(db, mes_referencia=_mes_referencia(mes))


@router.get("/evolucao-mensal", response_model=list[PontoEvolucaoMensal])
def evolucao_mensal(meses: int = 6, db: Session = Depends(get_db)) -> list[dict]:
    meses = max(1, min(meses, 24))
    return indicadores_service.evolucao_mensal(db, meses=meses)


@router.get("/por-centro-custo", response_model=list[ItemCentroCusto])
def por_centro_custo(
    tipo_operacao: TipoOperacaoNota = TipoOperacaoNota.entrada, mes: str | None = None, db: Session = Depends(get_db)
) -> list[dict]:
    return indicadores_service.por_centro_custo(db, tipo_operacao=tipo_operacao, mes_referencia=_mes_referencia(mes))


@router.get("/notas-por-status", response_model=list[ItemStatusNota])
def notas_por_status(db: Session = Depends(get_db)) -> list[dict]:
    return indicadores_service.notas_por_status(db)


@router.get("/gastos-previstos-por-dia", response_model=list[ItemGastoPrevistoDia])
def gastos_previstos_por_dia(mes: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    return indicadores_service.gastos_previstos_por_dia(db, _mes_referencia(mes) or date.today())
