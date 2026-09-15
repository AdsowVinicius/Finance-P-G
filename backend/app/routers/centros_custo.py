import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.database import get_db
from app.models.centro_custo import CentroCusto
from app.models.usuario import Usuario
from app.schemas.centro_custo import CentroCustoCreate, CentroCustoRead, CentroCustoUpdate
from app.services import auditoria_service

router = APIRouter(prefix="/centros-custo", tags=["centros de custo"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CentroCustoRead])
def listar_centros_custo(apenas_ativos: bool = True, db: Session = Depends(get_db)) -> list[CentroCusto]:
    query = db.query(CentroCusto)
    if apenas_ativos:
        query = query.filter(CentroCusto.ativo.is_(True))
    return query.order_by(CentroCusto.nome).all()


@router.get("/{centro_custo_id}", response_model=CentroCustoRead)
def obter_centro_custo(centro_custo_id: uuid.UUID, db: Session = Depends(get_db)) -> CentroCusto:
    centro_custo = db.get(CentroCusto, centro_custo_id)
    if centro_custo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centro de custo não encontrado")
    return centro_custo


@router.post("", response_model=CentroCustoRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)])
def criar_centro_custo(
    dados: CentroCustoCreate, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> CentroCusto:
    centro_custo = CentroCusto(**dados.model_dump())
    db.add(centro_custo)
    db.flush()
    auditoria_service.registrar_criacao(db, usuario_atual.id, "centros_custo", centro_custo)
    db.commit()
    db.refresh(centro_custo)
    return centro_custo


@router.put("/{centro_custo_id}", response_model=CentroCustoRead, dependencies=[Depends(require_write_access)])
def atualizar_centro_custo(
    centro_custo_id: uuid.UUID,
    dados: CentroCustoUpdate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> CentroCusto:
    centro_custo = db.get(CentroCusto, centro_custo_id)
    if centro_custo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centro de custo não encontrado")

    antes = auditoria_service.snapshot(centro_custo)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(centro_custo, campo, valor)

    auditoria_service.registrar_edicao(db, usuario_atual.id, "centros_custo", antes, centro_custo)
    db.commit()
    db.refresh(centro_custo)
    return centro_custo


@router.delete("/{centro_custo_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_write_access)])
def desativar_centro_custo(
    centro_custo_id: uuid.UUID, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> None:
    centro_custo = db.get(CentroCusto, centro_custo_id)
    if centro_custo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centro de custo não encontrado")
    antes = auditoria_service.snapshot(centro_custo)
    centro_custo.ativo = False
    auditoria_service.registrar_edicao(db, usuario_atual.id, "centros_custo", antes, centro_custo)
    db.commit()
