import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.database import get_db
from app.models.conta_financeira import ContaFinanceira
from app.models.enums import StatusPreLancamentoWhatsapp
from app.models.pre_lancamento_whatsapp import PreLancamentoWhatsapp
from app.models.usuario import Usuario
from app.schemas.conta_financeira import ContaFinanceiraRead
from app.schemas.pre_lancamento_whatsapp import ConfirmarPreLancamento, PreLancamentoWhatsappRead
from app.services import auditoria_service
from app.services.dia_util_calculator import DiaUtilCalculator

router = APIRouter(prefix="/pre-lancamentos-whatsapp", tags=["whatsapp"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[PreLancamentoWhatsappRead])
def listar(
    status_filtro: StatusPreLancamentoWhatsapp = StatusPreLancamentoWhatsapp.pendente_revisao,
    db: Session = Depends(get_db),
) -> list[PreLancamentoWhatsapp]:
    return (
        db.query(PreLancamentoWhatsapp)
        .filter(PreLancamentoWhatsapp.status == status_filtro)
        .order_by(PreLancamentoWhatsapp.created_at.desc())
        .all()
    )


@router.post(
    "/{pre_id}/confirmar", response_model=ContaFinanceiraRead, dependencies=[Depends(require_write_access)]
)
def confirmar(
    pre_id: uuid.UUID,
    dados: ConfirmarPreLancamento,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> ContaFinanceira:
    pre = db.get(PreLancamentoWhatsapp, pre_id)
    if pre is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pré-lançamento não encontrado")
    if pre.status != StatusPreLancamentoWhatsapp.pendente_revisao:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pré-lançamento já foi revisado")

    data_ajustada = DiaUtilCalculator().proximo_dia_util(dados.data_vencimento)
    conta = ContaFinanceira(
        tipo_operacao=pre.tipo_operacao,
        parceiro_id=dados.parceiro_id,
        centro_custo_id=dados.centro_custo_id,
        descricao=dados.descricao,
        valor=dados.valor,
        data_vencimento_original=dados.data_vencimento,
        data_vencimento=data_ajustada,
        conta_bancaria_id=dados.conta_bancaria_id,
        forma_pagamento=dados.forma_pagamento,
        criado_por=usuario_atual.id,
    )
    db.add(conta)
    db.flush()
    auditoria_service.registrar_criacao(db, usuario_atual.id, "contas_financeiras", conta)

    antes_pre = auditoria_service.snapshot(pre)
    pre.status = StatusPreLancamentoWhatsapp.confirmado
    pre.parceiro_id = dados.parceiro_id
    pre.centro_custo_id = dados.centro_custo_id
    pre.conta_financeira_id = conta.id
    if dados.forma_pagamento is not None:
        pre.forma_pagamento = dados.forma_pagamento
    auditoria_service.registrar_edicao(db, usuario_atual.id, "pre_lancamentos_whatsapp", antes_pre, pre)

    db.commit()
    db.refresh(conta)
    return conta


@router.post(
    "/{pre_id}/descartar", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_write_access)]
)
def descartar(
    pre_id: uuid.UUID, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> None:
    pre = db.get(PreLancamentoWhatsapp, pre_id)
    if pre is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pré-lançamento não encontrado")
    if pre.status != StatusPreLancamentoWhatsapp.pendente_revisao:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pré-lançamento já foi revisado")

    antes = auditoria_service.snapshot(pre)
    pre.status = StatusPreLancamentoWhatsapp.descartado
    auditoria_service.registrar_edicao(db, usuario_atual.id, "pre_lancamentos_whatsapp", antes, pre)
    db.commit()
