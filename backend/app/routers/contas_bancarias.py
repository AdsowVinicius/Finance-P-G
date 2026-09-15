import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.database import get_db
from app.models.conta_bancaria import ContaBancaria
from app.models.usuario import Usuario
from app.schemas.conta_bancaria import ContaBancariaCreate, ContaBancariaRead, ContaBancariaUpdate
from app.services import auditoria_service

router = APIRouter(prefix="/contas-bancarias", tags=["contas bancárias"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ContaBancariaRead])
def listar_contas_bancarias(apenas_ativas: bool = True, db: Session = Depends(get_db)) -> list[ContaBancaria]:
    query = db.query(ContaBancaria)
    if apenas_ativas:
        query = query.filter(ContaBancaria.ativo.is_(True))
    return query.order_by(ContaBancaria.apelido).all()


@router.get("/{conta_bancaria_id}", response_model=ContaBancariaRead)
def obter_conta_bancaria(conta_bancaria_id: uuid.UUID, db: Session = Depends(get_db)) -> ContaBancaria:
    conta = db.get(ContaBancaria, conta_bancaria_id)
    if conta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta bancária não encontrada")
    return conta


@router.post("", response_model=ContaBancariaRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def criar_conta_bancaria(
    dados: ContaBancariaCreate, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> ContaBancaria:
    conta = ContaBancaria(**dados.model_dump())
    db.add(conta)
    db.flush()
    auditoria_service.registrar_criacao(db, usuario_atual.id, "contas_bancarias", conta)
    db.commit()
    db.refresh(conta)
    return conta


@router.put("/{conta_bancaria_id}", response_model=ContaBancariaRead, dependencies=[Depends(require_write_access)])
def atualizar_conta_bancaria(
    conta_bancaria_id: uuid.UUID,
    dados: ContaBancariaUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> ContaBancaria:
    conta = db.get(ContaBancaria, conta_bancaria_id)
    if conta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta bancária não encontrada")

    antes = auditoria_service.snapshot(conta)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(conta, campo, valor)

    auditoria_service.registrar_edicao(db, usuario_atual.id, "contas_bancarias", antes, conta)
    db.commit()
    db.refresh(conta)
    return conta


@router.delete("/{conta_bancaria_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_write_access)])
def desativar_conta_bancaria(
    conta_bancaria_id: uuid.UUID, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> None:
    conta = db.get(ContaBancaria, conta_bancaria_id)
    if conta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta bancária não encontrada")
    antes = auditoria_service.snapshot(conta)
    conta.ativo = False
    auditoria_service.registrar_edicao(db, usuario_atual.id, "contas_bancarias", antes, conta)
    db.commit()
