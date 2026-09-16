"""Regra de negócio de contas_financeiras que não cabe em nenhum dos
serviços de domínio mais específicos (RecorrenciaService, ConciliacaoMatcher
etc.) — hoje só a marcação em lote de contas atrasadas.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conta_financeira import ContaFinanceira
from app.models.enums import StatusConta
from app.services import auditoria_service


def marcar_atrasadas(db: Session, usuario_id: uuid.UUID) -> list[ContaFinanceira]:
    """Marca como 'atrasado' toda conta pendente cuja data_vencimento já
    passou, registrando um log de auditoria de edição por conta alterada
    (mudança de status em massa é sensível o suficiente pra deixar rastro,
    igual qualquer outra edição de contas_financeiras). Não commita — o
    chamador decide a transação.
    """
    hoje = date.today()
    contas = (
        db.execute(
            select(ContaFinanceira).where(
                ContaFinanceira.status == StatusConta.pendente, ContaFinanceira.data_vencimento < hoje
            )
        )
        .scalars()
        .all()
    )
    for conta in contas:
        antes = auditoria_service.snapshot(conta)
        conta.status = StatusConta.atrasado
        auditoria_service.registrar_edicao(db, usuario_id, "contas_financeiras", antes, conta)
    return list(contas)
