import csv
import io
import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.core.storage import salvar_arquivo_upload
from app.database import get_db
from app.models.conta_financeira import ContaFinanceira
from app.models.enums import FormaBaixa, FormaPagamento, StatusConta, TipoOperacaoNota
from app.models.parceiro import Parceiro
from app.models.usuario import Usuario
from app.services import auditoria_service
from app.services.dia_util_calculator import DiaUtilCalculator
from app.services.nota_fiscal_service import atualizar_status_conciliacao
from app.schemas.conta_financeira import (
    ContaFinanceiraBaixa,
    ContaFinanceiraCreate,
    ContaFinanceiraRead,
    DashboardVencimentoResponse,
)

router = APIRouter(prefix="/contas-financeiras", tags=["contas a pagar/receber"], dependencies=[Depends(get_current_user)])


def _query_relatorio(
    db: Session,
    tipo_operacao: TipoOperacaoNota | None,
    status_conta: StatusConta | None,
    parceiro_id: uuid.UUID | None,
    centro_custo_id: uuid.UUID | None,
    nota_fiscal_id: uuid.UUID | None,
    lancamento_recorrente_id: uuid.UUID | None,
    forma_pagamento: FormaPagamento | None,
    data_inicio: date | None,
    data_fim: date | None,
    valor_min: Decimal | None,
    valor_max: Decimal | None,
    busca: str | None,
):
    query = db.query(ContaFinanceira)
    if tipo_operacao is not None:
        query = query.filter(ContaFinanceira.tipo_operacao == tipo_operacao)
    if status_conta is not None:
        query = query.filter(ContaFinanceira.status == status_conta)
    if parceiro_id is not None:
        query = query.filter(ContaFinanceira.parceiro_id == parceiro_id)
    if centro_custo_id is not None:
        query = query.filter(ContaFinanceira.centro_custo_id == centro_custo_id)
    if nota_fiscal_id is not None:
        query = query.filter(ContaFinanceira.nota_fiscal_id == nota_fiscal_id)
    if lancamento_recorrente_id is not None:
        query = query.filter(ContaFinanceira.lancamento_recorrente_id == lancamento_recorrente_id)
    if forma_pagamento is not None:
        query = query.filter(ContaFinanceira.forma_pagamento == forma_pagamento)
    if data_inicio is not None:
        query = query.filter(ContaFinanceira.data_vencimento >= data_inicio)
    if data_fim is not None:
        query = query.filter(ContaFinanceira.data_vencimento <= data_fim)
    if valor_min is not None:
        query = query.filter(ContaFinanceira.valor >= valor_min)
    if valor_max is not None:
        query = query.filter(ContaFinanceira.valor <= valor_max)
    if busca:
        query = query.filter(ContaFinanceira.descricao.ilike(f"%{busca}%"))
    return query


@router.get("", response_model=list[ContaFinanceiraRead])
def listar_contas_financeiras(
    tipo_operacao: TipoOperacaoNota | None = None,
    status_conta: StatusConta | None = None,
    parceiro_id: uuid.UUID | None = None,
    centro_custo_id: uuid.UUID | None = None,
    nota_fiscal_id: uuid.UUID | None = None,
    lancamento_recorrente_id: uuid.UUID | None = None,
    forma_pagamento: FormaPagamento | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    valor_min: Decimal | None = None,
    valor_max: Decimal | None = None,
    busca: str | None = None,
    db: Session = Depends(get_db),
) -> list[ContaFinanceira]:
    query = _query_relatorio(
        db,
        tipo_operacao,
        status_conta,
        parceiro_id,
        centro_custo_id,
        nota_fiscal_id,
        lancamento_recorrente_id,
        forma_pagamento,
        data_inicio,
        data_fim,
        valor_min,
        valor_max,
        busca,
    )
    return query.order_by(ContaFinanceira.data_vencimento.desc()).all()


@router.get("/exportar-csv")
def exportar_csv(
    tipo_operacao: TipoOperacaoNota | None = None,
    status_conta: StatusConta | None = None,
    parceiro_id: uuid.UUID | None = None,
    centro_custo_id: uuid.UUID | None = None,
    nota_fiscal_id: uuid.UUID | None = None,
    lancamento_recorrente_id: uuid.UUID | None = None,
    forma_pagamento: FormaPagamento | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    valor_min: Decimal | None = None,
    valor_max: Decimal | None = None,
    busca: str | None = None,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Mesmos filtros do GET /contas-financeiras, exportados em CSV."""
    query = _query_relatorio(
        db,
        tipo_operacao,
        status_conta,
        parceiro_id,
        centro_custo_id,
        nota_fiscal_id,
        lancamento_recorrente_id,
        forma_pagamento,
        data_inicio,
        data_fim,
        valor_min,
        valor_max,
        busca,
    )
    linhas = (
        query.join(Parceiro, ContaFinanceira.parceiro_id == Parceiro.id)
        .with_entities(
            ContaFinanceira.tipo_operacao,
            ContaFinanceira.descricao,
            Parceiro.razao_social,
            ContaFinanceira.valor,
            ContaFinanceira.valor_pago,
            ContaFinanceira.data_vencimento,
            ContaFinanceira.data_pagamento,
            ContaFinanceira.status,
            ContaFinanceira.forma_pagamento,
            ContaFinanceira.numero_parcela,
            ContaFinanceira.total_parcelas,
        )
        .order_by(ContaFinanceira.data_vencimento.desc())
        .all()
    )

    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";")
    escritor.writerow(
        [
            "Tipo",
            "Descrição",
            "Parceiro",
            "Valor",
            "Valor pago",
            "Juros/Desconto",
            "Vencimento",
            "Pagamento",
            "Status",
            "Forma de pagamento",
            "Parcela",
        ]
    )
    for linha in linhas:
        juros = linha.valor_pago - linha.valor if linha.valor_pago is not None else None
        escritor.writerow(
            [
                "Despesa" if linha.tipo_operacao == TipoOperacaoNota.entrada else "Receita",
                linha.descricao,
                linha.razao_social,
                str(linha.valor).replace(".", ","),
                str(linha.valor_pago).replace(".", ",") if linha.valor_pago is not None else "",
                str(juros).replace(".", ",") if juros is not None else "",
                linha.data_vencimento.isoformat(),
                linha.data_pagamento.isoformat() if linha.data_pagamento else "",
                linha.status.value,
                linha.forma_pagamento.value if linha.forma_pagamento else "",
                f"{linha.numero_parcela}/{linha.total_parcelas}",
            ]
        )

    buffer.seek(0)
    nome_arquivo = f"lancamentos_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/dashboard", response_model=DashboardVencimentoResponse)
def dashboard_vencimento(
    tipo_operacao: TipoOperacaoNota | None = None, db: Session = Depends(get_db)
) -> DashboardVencimentoResponse:
    """RF11: painel de contas a pagar/receber por prazo de vencimento
    (vencendo hoje, na semana, em atraso). Usa o índice
    idx_contas_vencimento_status (data_vencimento, status).
    """
    hoje = date.today()
    fim_semana = hoje + timedelta(days=7)

    query = db.query(ContaFinanceira).filter(ContaFinanceira.status.in_([StatusConta.pendente, StatusConta.atrasado]))
    if tipo_operacao is not None:
        query = query.filter(ContaFinanceira.tipo_operacao == tipo_operacao)

    atrasado = query.filter(ContaFinanceira.data_vencimento < hoje).order_by(ContaFinanceira.data_vencimento).all()
    hoje_lista = query.filter(ContaFinanceira.data_vencimento == hoje).order_by(ContaFinanceira.descricao).all()
    semana = (
        query.filter(ContaFinanceira.data_vencimento > hoje, ContaFinanceira.data_vencimento <= fim_semana)
        .order_by(ContaFinanceira.data_vencimento)
        .all()
    )

    def total(contas: list[ContaFinanceira]) -> Decimal:
        return sum((c.valor for c in contas), Decimal("0"))

    return DashboardVencimentoResponse(
        atrasado=atrasado,
        hoje=hoje_lista,
        semana=semana,
        total_atrasado=total(atrasado),
        total_hoje=total(hoje_lista),
        total_semana=total(semana),
    )


@router.post(
    "/atualizar-atrasados",
    dependencies=[Depends(require_write_access)],
)
def atualizar_atrasados(db: Session = Depends(get_db)) -> dict[str, int]:
    """Botão manual (Celery Beat fica pra depois): marca como 'atrasado'
    toda conta pendente cuja data_vencimento já passou.
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
        conta.status = StatusConta.atrasado
    db.commit()
    return {"atualizadas": len(contas)}


@router.get("/{conta_id}", response_model=ContaFinanceiraRead)
def obter_conta_financeira(conta_id: uuid.UUID, db: Session = Depends(get_db)) -> ContaFinanceira:
    conta = db.get(ContaFinanceira, conta_id)
    if conta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada")
    return conta


@router.post(
    "", response_model=ContaFinanceiraRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)]
)
def criar_conta_financeira_manual(
    dados: ContaFinanceiraCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> ContaFinanceira:
    data_ajustada = DiaUtilCalculator().proximo_dia_util(dados.data_vencimento)
    conta = ContaFinanceira(
        tipo_operacao=dados.tipo_operacao,
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
    db.commit()
    db.refresh(conta)
    return conta


@router.post("/{conta_id}/baixa", response_model=ContaFinanceiraRead, dependencies=[Depends(require_write_access)])
def dar_baixa_manual(
    conta_id: uuid.UUID,
    dados: ContaFinanceiraBaixa,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> ContaFinanceira:
    conta = db.get(ContaFinanceira, conta_id)
    if conta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada")
    if conta.status == StatusConta.pago:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conta já está paga")

    antes = auditoria_service.snapshot(conta)
    conta.data_pagamento = dados.data_pagamento
    conta.valor_pago = dados.valor_pago
    conta.status = StatusConta.pago
    conta.forma_baixa = FormaBaixa.manual
    if dados.forma_pagamento is not None:
        conta.forma_pagamento = dados.forma_pagamento
    if dados.conta_bancaria_id is not None:
        conta.conta_bancaria_id = dados.conta_bancaria_id

    atualizar_status_conciliacao(db, conta.nota_fiscal_id)
    auditoria_service.registrar_edicao(db, usuario_atual.id, "contas_financeiras", antes, conta)
    db.commit()
    db.refresh(conta)
    return conta


@router.post("/{conta_id}/boleto", response_model=ContaFinanceiraRead, dependencies=[Depends(require_write_access)])
async def anexar_boleto(
    conta_id: uuid.UUID,
    arquivo: UploadFile = File(...),
    linha_digitavel: str | None = Form(None),
    codigo_barras: str | None = Form(None),
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> ContaFinanceira:
    conta = db.get(ContaFinanceira, conta_id)
    if conta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada")

    conteudo = await arquivo.read()
    try:
        caminho = salvar_arquivo_upload(arquivo, "boletos", conteudo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    antes = auditoria_service.snapshot(conta)
    conta.boleto_arquivo_path = caminho
    conta.boleto_linha_digitavel = linha_digitavel
    conta.boleto_codigo_barras = codigo_barras
    auditoria_service.registrar_edicao(db, usuario_atual.id, "contas_financeiras", antes, conta)
    db.commit()
    db.refresh(conta)
    return conta
