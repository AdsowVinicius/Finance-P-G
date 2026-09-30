"""Sincronização Open Finance (Pluggy) -> lançamentos de extrato.

Cada sincronização vira um `ExtratoImportado` (formato `open_finance`, sem
arquivo) e passa pelo mesmo caminho do OFX/CSV (`persistir_e_conciliar`):
idempotente por (conta, fitid) e com conciliação automática. A janela
reaproveita os últimos dias (sobreposição) porque o banco pode liberar
transações com atraso — a idempotência torna a sobreposição inofensiva.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.conta_bancaria import ContaBancaria
from app.models.enums import FormatoExtrato, StatusImportacao
from app.models.extrato_importado import ExtratoImportado
from app.services.importacao_extrato_service import persistir_e_conciliar
from app.services.pluggy_client import PluggyClient, PluggyError

JANELA_INICIAL_DIAS = 90
SOBREPOSICAO_DIAS = 7


@dataclass
class ResultadoSincronizacaoConta:
    ok: bool
    novos: int = 0
    erro: str | None = None
    extrato_id: object | None = None


def sincronizar_conta(db: Session, conta: ContaBancaria, cliente: PluggyClient) -> ResultadoSincronizacaoConta:
    if not conta.open_finance_conta_id:
        return ResultadoSincronizacaoConta(ok=False, erro="conta bancária não está vinculada ao Open Finance")

    hoje = date.today()
    if conta.open_finance_sincronizado_em:
        desde = conta.open_finance_sincronizado_em.date() - timedelta(days=SOBREPOSICAO_DIAS)
    else:
        desde = hoje - timedelta(days=JANELA_INICIAL_DIAS)

    try:
        dtos = cliente.listar_transacoes(conta.open_finance_conta_id, desde, hoje)
    except PluggyError as exc:
        return ResultadoSincronizacaoConta(ok=False, erro=str(exc))

    extrato = ExtratoImportado(
        conta_bancaria_id=conta.id,
        arquivo_original_path=f"open_finance:{conta.open_finance_conta_id}",
        formato=FormatoExtrato.open_finance,
        periodo_inicio=desde,
        periodo_fim=hoje,
        status=StatusImportacao.processando,
    )
    db.add(extrato)
    db.flush()

    novos = persistir_e_conciliar(db, extrato, dtos)
    conta.open_finance_sincronizado_em = datetime.now(timezone.utc)
    if novos == 0:
        # nada novo: não deixa um extrato vazio poluindo a listagem a cada rodada agendada
        db.delete(extrato)
        db.commit()
        return ResultadoSincronizacaoConta(ok=True, novos=0)

    extrato.status = StatusImportacao.concluido
    db.commit()
    return ResultadoSincronizacaoConta(ok=True, novos=novos, extrato_id=extrato.id)
