import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.database import get_db
from app.models.parceiro import Parceiro
from app.models.usuario import Usuario
from app.schemas.parceiro import ParceiroCreate, ParceiroRead, ParceiroUpdate
from app.services import auditoria_service
from app.services.nota_fiscal_service import CNPJ_SENTINELA

router = APIRouter(prefix="/parceiros", tags=["parceiros"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ParceiroRead])
def listar_parceiros(apenas_ativos: bool = True, db: Session = Depends(get_db)) -> list[Parceiro]:
    # o parceiro sentinela é um placeholder interno (nota fiscal aguardando
    # a API resolver o fornecedor real) — nunca deve aparecer pro usuário.
    query = db.query(Parceiro).filter(Parceiro.cnpj_cpf != CNPJ_SENTINELA)
    if apenas_ativos:
        query = query.filter(Parceiro.ativo.is_(True))
    return query.order_by(Parceiro.razao_social).all()


@router.get("/{parceiro_id}", response_model=ParceiroRead)
def obter_parceiro(parceiro_id: uuid.UUID, db: Session = Depends(get_db)) -> Parceiro:
    parceiro = db.get(Parceiro, parceiro_id)
    if parceiro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parceiro não encontrado")
    return parceiro


@router.post("", response_model=ParceiroRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def criar_parceiro(
    dados: ParceiroCreate, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> Parceiro:
    parceiro = Parceiro(**dados.model_dump())
    db.add(parceiro)
    db.flush()
    auditoria_service.registrar_criacao(db, usuario_atual.id, "parceiros", parceiro)
    db.commit()
    db.refresh(parceiro)
    return parceiro


@router.put("/{parceiro_id}", response_model=ParceiroRead, dependencies=[Depends(require_write_access)])
def atualizar_parceiro(
    parceiro_id: uuid.UUID,
    dados: ParceiroUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> Parceiro:
    parceiro = db.get(Parceiro, parceiro_id)
    if parceiro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parceiro não encontrado")

    antes = auditoria_service.snapshot(parceiro)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(parceiro, campo, valor)

    auditoria_service.registrar_edicao(db, usuario_atual.id, "parceiros", antes, parceiro)
    db.commit()
    db.refresh(parceiro)
    return parceiro


@router.delete("/{parceiro_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_write_access)])
def desativar_parceiro(
    parceiro_id: uuid.UUID, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> None:
    parceiro = db.get(Parceiro, parceiro_id)
    if parceiro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parceiro não encontrado")
    antes = auditoria_service.snapshot(parceiro)
    parceiro.ativo = False
    auditoria_service.registrar_edicao(db, usuario_atual.id, "parceiros", antes, parceiro)
    db.commit()
