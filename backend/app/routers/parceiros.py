import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.database import get_db
from app.models.parceiro import Parceiro
from app.schemas.parceiro import ParceiroCreate, ParceiroRead, ParceiroUpdate
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
def criar_parceiro(dados: ParceiroCreate, db: Session = Depends(get_db)) -> Parceiro:
    parceiro = Parceiro(**dados.model_dump())
    db.add(parceiro)
    db.commit()
    db.refresh(parceiro)
    return parceiro


@router.put("/{parceiro_id}", response_model=ParceiroRead, dependencies=[Depends(require_write_access)])
def atualizar_parceiro(parceiro_id: uuid.UUID, dados: ParceiroUpdate, db: Session = Depends(get_db)) -> Parceiro:
    parceiro = db.get(Parceiro, parceiro_id)
    if parceiro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parceiro não encontrado")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(parceiro, campo, valor)

    db.commit()
    db.refresh(parceiro)
    return parceiro


@router.delete("/{parceiro_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_write_access)])
def desativar_parceiro(parceiro_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    parceiro = db.get(Parceiro, parceiro_id)
    if parceiro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parceiro não encontrado")
    parceiro.ativo = False
    db.commit()
