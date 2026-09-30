import uuid
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.database import get_db
from app.models.conexao_open_finance import ConexaoOpenFinance
from app.models.conta_bancaria import ContaBancaria
from app.models.usuario import Usuario
from app.schemas.integracoes import (
    ConectarItemRequest,
    ConexaoOpenFinanceRead,
    ConnectTokenRead,
    ContaRemotaRead,
    ContaVinculadaRead,
    EnfileiradoRead,
    OpenFinanceStatus,
    VincularContaRequest,
)
from app.services import auditoria_service
from app.services.pluggy_client import PluggyClient, PluggyError, PluggyNaoConfigurado
from app.workers.tasks import sincronizar_open_finance_conta

router = APIRouter(prefix="/open-finance", tags=["open finance"], dependencies=[Depends(get_current_user)])


def get_pluggy() -> PluggyClient:
    cliente = PluggyClient()
    if not cliente.configurado:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="PLUGGY_CLIENT_ID/PLUGGY_CLIENT_SECRET não configurados")
    return cliente


def _erro_pluggy(exc: PluggyError) -> HTTPException:
    codigo = status.HTTP_503_SERVICE_UNAVAILABLE if isinstance(exc, PluggyNaoConfigurado) else status.HTTP_502_BAD_GATEWAY
    return HTTPException(codigo, detail=str(exc))


@router.get("/status", response_model=OpenFinanceStatus)
def status_open_finance(db: Session = Depends(get_db)) -> OpenFinanceStatus:
    conexoes = db.query(ConexaoOpenFinance).order_by(ConexaoOpenFinance.created_at.desc()).all()
    vinculadas = (
        db.query(ContaBancaria)
        .filter(ContaBancaria.open_finance_conta_id.isnot(None))
        .order_by(ContaBancaria.apelido)
        .all()
    )
    return OpenFinanceStatus(
        configurado=PluggyClient().configurado,
        conexoes=[ConexaoOpenFinanceRead.model_validate(c) for c in conexoes],
        contas_vinculadas=[ContaVinculadaRead.model_validate(c) for c in vinculadas],
    )


@router.post("/connect-token", response_model=ConnectTokenRead)
def gerar_connect_token(
    item_id: str | None = None,
    usuario_atual: Usuario = Depends(get_current_user),
    cliente: PluggyClient = Depends(get_pluggy),
) -> ConnectTokenRead:
    """Token curto pro frontend abrir o Pluggy Connect. `item_id` opcional
    pra reconectar/atualizar um banco já conectado."""
    try:
        return ConnectTokenRead(access_token=cliente.criar_connect_token(str(usuario_atual.id), item_id))
    except PluggyError as exc:
        raise _erro_pluggy(exc) from exc


@router.post(
    "/conexoes",
    response_model=ConexaoOpenFinanceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
)
def registrar_conexao(
    dados: ConectarItemRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
    cliente: PluggyClient = Depends(get_pluggy),
) -> ConexaoOpenFinance:
    """Chamado pelo frontend com o `itemId` que o widget devolveu no onSuccess."""
    existente = db.query(ConexaoOpenFinance).filter(ConexaoOpenFinance.item_id == dados.item_id).first()
    if existente is not None:
        return existente
    try:
        item = cliente.obter_item(dados.item_id)  # confirma que o item existe nas nossas credenciais
    except PluggyError as exc:
        raise _erro_pluggy(exc) from exc

    conexao = ConexaoOpenFinance(
        item_id=dados.item_id,
        conector_nome=(item.get("connector") or {}).get("name"),
        status=item.get("status"),
        criado_por=usuario_atual.id,
    )
    db.add(conexao)
    db.flush()
    auditoria_service.registrar_criacao(db, usuario_atual.id, "conexoes_open_finance", conexao)
    db.commit()
    db.refresh(conexao)
    return conexao


@router.get("/conexoes/{conexao_id}/contas", response_model=list[ContaRemotaRead])
def listar_contas_remotas(
    conexao_id: uuid.UUID, db: Session = Depends(get_db), cliente: PluggyClient = Depends(get_pluggy)
) -> list[ContaRemotaRead]:
    conexao = db.get(ConexaoOpenFinance, conexao_id)
    if conexao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conexão não encontrada")
    try:
        contas = cliente.listar_contas(conexao.item_id)
    except PluggyError as exc:
        raise _erro_pluggy(exc) from exc

    def _saldo(valor) -> Decimal | None:
        try:
            return Decimal(str(valor)) if valor is not None else None
        except InvalidOperation:
            return None

    return [
        ContaRemotaRead(
            id=c["id"],
            nome=c.get("name") or c.get("marketingName"),
            tipo=c.get("type"),
            subtipo=c.get("subtype"),
            numero=c.get("number"),
            saldo=_saldo(c.get("balance")),
        )
        for c in contas
    ]


@router.post(
    "/contas-bancarias/{conta_bancaria_id}/vincular",
    response_model=ContaVinculadaRead,
    dependencies=[Depends(require_write_access)],
)
def vincular_conta(
    conta_bancaria_id: uuid.UUID,
    dados: VincularContaRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> ContaBancaria:
    conta = db.get(ContaBancaria, conta_bancaria_id)
    if conta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conta bancária não encontrada")
    if db.get(ConexaoOpenFinance, dados.conexao_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conexão não encontrada")

    em_uso = (
        db.query(ContaBancaria)
        .filter(ContaBancaria.open_finance_conta_id == dados.open_finance_conta_id, ContaBancaria.id != conta.id)
        .first()
    )
    if em_uso is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Essa conta remota já está vinculada a '{em_uso.apelido}'")

    antes = auditoria_service.snapshot(conta)
    conta.conexao_open_finance_id = dados.conexao_id
    conta.open_finance_conta_id = dados.open_finance_conta_id
    conta.open_finance_sincronizado_em = None  # primeira sincronização busca a janela inicial
    auditoria_service.registrar_edicao(db, usuario_atual.id, "contas_bancarias", antes, conta)
    db.commit()
    db.refresh(conta)
    return conta


@router.delete(
    "/contas-bancarias/{conta_bancaria_id}/vincular",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_write_access)],
)
def desvincular_conta(
    conta_bancaria_id: uuid.UUID, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> None:
    conta = db.get(ContaBancaria, conta_bancaria_id)
    if conta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conta bancária não encontrada")
    antes = auditoria_service.snapshot(conta)
    conta.conexao_open_finance_id = None
    conta.open_finance_conta_id = None
    conta.open_finance_sincronizado_em = None
    auditoria_service.registrar_edicao(db, usuario_atual.id, "contas_bancarias", antes, conta)
    db.commit()


@router.post(
    "/contas-bancarias/{conta_bancaria_id}/sincronizar",
    response_model=EnfileiradoRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_write_access)],
)
def sincronizar_conta_bancaria(conta_bancaria_id: uuid.UUID, db: Session = Depends(get_db)) -> EnfileiradoRead:
    conta = db.get(ContaBancaria, conta_bancaria_id)
    if conta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conta bancária não encontrada")
    if not conta.open_finance_conta_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Conta não está vinculada ao Open Finance")
    sincronizar_open_finance_conta.delay(str(conta.id))
    return EnfileiradoRead(mensagem="Sincronização enfileirada")
