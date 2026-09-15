from datetime import date

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user

router = APIRouter(prefix="/sistema", tags=["sistema"], dependencies=[Depends(get_current_user)])


@router.get("/data-atual")
def data_atual() -> dict[str, str]:
    """Data de hoje segundo o relógio do servidor — usado pelo frontend pra
    presetar filtros de período (ex: mês corrente em Relatórios) sem
    depender do relógio/fuso do navegador do usuário."""
    return {"data": date.today().isoformat()}
