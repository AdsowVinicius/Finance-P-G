import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.database import get_db
from app.models.lancamento_recorrente import LancamentoRecorrente
from app.models.usuario import Usuario
from app.schemas.lancamento_recorrente import LancamentoRecorrenteCreate, LancamentoRecorrenteRead
from app.services.recorrencia_service import RecorrenciaService

router = APIRouter(
    prefix="/lancamentos-recorrentes", tags=["lançamentos recorrentes"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[LancamentoRecorrenteRead])
def listar_lancamentos_recorrentes(apenas_ativos: bool = True, db: Session = Depends(get_db)) -> list[LancamentoRecorrente]:
    query = db.query(LancamentoRecorrente)
    if apenas_ativos:
        query = query.filter(LancamentoRecorrente.ativo.is_(True))
    return query.order_by(LancamentoRecorrente.data_inicio.desc()).all()


@router.get("/{lancamento_id}", response_model=LancamentoRecorrenteRead)
def obter_lancamento_recorrente(lancamento_id: uuid.UUID, db: Session = Depends(get_db)) -> LancamentoRecorrente:
    lancamento = db.get(LancamentoRecorrente, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lançamento recorrente não encontrado")
    return lancamento


@router.post(
    "",
    response_model=LancamentoRecorrenteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
)
def criar_lancamento_recorrente(
    dados: LancamentoRecorrenteCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> LancamentoRecorrente:
    lancamento = LancamentoRecorrente(**dados.model_dump(), criado_por=usuario_atual.id)
    db.add(lancamento)
    db.flush()  # garante lancamento.id antes de gerar as parcelas

    parcelas = RecorrenciaService().gerar_parcelas(lancamento)
    db.add_all(parcelas)

    db.commit()
    db.refresh(lancamento)
    return lancamento


@router.delete("/{lancamento_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_write_access)])
def desativar_lancamento_recorrente(lancamento_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    """Desativa a recorrência (não gera mais parcelas futuras). Não apaga
    as parcelas (contas_financeiras) já geradas — preserva histórico.
    """
    lancamento = db.get(LancamentoRecorrente, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lançamento recorrente não encontrado")
    lancamento.ativo = False
    db.commit()
