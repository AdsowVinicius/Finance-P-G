import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.database import get_db
from app.models.centro_custo import CentroCusto
from app.models.nota_centro_custo import NotaCentroCusto
from app.models.orcamento_centro_custo import OrcamentoCentroCusto
from app.models.usuario import Usuario
from app.schemas.nota_centro_custo import NotaCentroCustoCreate, NotaCentroCustoRead
from app.schemas.orcamento_centro_custo import (
    OrcamentoCentroCustoRead,
    OrcamentoCentroCustoUpsert,
    PontoCurvaS,
    ResumoCentroCusto,
)
from app.services import analise_centro_custo_service, auditoria_service

router = APIRouter(
    prefix="/centros-custo/{centro_custo_id}", tags=["análise por centro de custo"], dependencies=[Depends(get_current_user)]
)


def _obter_centro_ou_404(db: Session, centro_custo_id: uuid.UUID) -> CentroCusto:
    centro = db.get(CentroCusto, centro_custo_id)
    if centro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centro de custo não encontrado")
    return centro


@router.get("/resumo", response_model=ResumoCentroCusto)
def resumo(centro_custo_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    _obter_centro_ou_404(db, centro_custo_id)
    return analise_centro_custo_service.resumo_centro_custo(db, centro_custo_id)


@router.get("/curva-s", response_model=list[PontoCurvaS])
def curva_s(centro_custo_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    _obter_centro_ou_404(db, centro_custo_id)
    return analise_centro_custo_service.curva_s(db, centro_custo_id)


@router.get("/orcamento", response_model=list[OrcamentoCentroCustoRead])
def listar_orcamento(centro_custo_id: uuid.UUID, db: Session = Depends(get_db)) -> list[OrcamentoCentroCusto]:
    _obter_centro_ou_404(db, centro_custo_id)
    return (
        db.query(OrcamentoCentroCusto)
        .filter(OrcamentoCentroCusto.centro_custo_id == centro_custo_id)
        .order_by(OrcamentoCentroCusto.mes_referencia)
        .all()
    )


@router.put("/orcamento", response_model=OrcamentoCentroCustoRead, dependencies=[Depends(require_write_access)])
def definir_orcamento_do_mes(
    centro_custo_id: uuid.UUID,
    dados: OrcamentoCentroCustoUpsert,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> OrcamentoCentroCusto:
    """Upsert: um PUT por mês (o frontend edita célula a célula numa
    tabelinha de meses). mes_referencia é normalizado pro dia 1.
    """
    _obter_centro_ou_404(db, centro_custo_id)
    mes = dados.mes_referencia.replace(day=1)

    existente = (
        db.query(OrcamentoCentroCusto)
        .filter(OrcamentoCentroCusto.centro_custo_id == centro_custo_id, OrcamentoCentroCusto.mes_referencia == mes)
        .first()
    )
    if existente is not None:
        antes = auditoria_service.snapshot(existente)
        existente.valor_planejado = dados.valor_planejado
        auditoria_service.registrar_edicao(db, usuario_atual.id, "orcamentos_centro_custo", antes, existente)
        db.commit()
        db.refresh(existente)
        return existente

    novo = OrcamentoCentroCusto(centro_custo_id=centro_custo_id, mes_referencia=mes, valor_planejado=dados.valor_planejado)
    db.add(novo)
    db.flush()
    auditoria_service.registrar_criacao(db, usuario_atual.id, "orcamentos_centro_custo", novo)
    db.commit()
    db.refresh(novo)
    return novo


@router.get("/notas", response_model=list[NotaCentroCustoRead])
def listar_notas(centro_custo_id: uuid.UUID, db: Session = Depends(get_db)) -> list[NotaCentroCustoRead]:
    _obter_centro_ou_404(db, centro_custo_id)
    linhas = (
        db.query(NotaCentroCusto, Usuario.nome)
        .join(Usuario, Usuario.id == NotaCentroCusto.usuario_id)
        .filter(NotaCentroCusto.centro_custo_id == centro_custo_id)
        .order_by(NotaCentroCusto.created_at.desc())
        .all()
    )
    return [
        NotaCentroCustoRead(
            id=nota.id,
            centro_custo_id=nota.centro_custo_id,
            usuario_id=nota.usuario_id,
            usuario_nome=nome,
            texto=nota.texto,
            created_at=nota.created_at,
        )
        for nota, nome in linhas
    ]


@router.post(
    "/notas", response_model=NotaCentroCustoRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_write_access)]
)
def criar_nota(
    centro_custo_id: uuid.UUID,
    dados: NotaCentroCustoCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> NotaCentroCustoRead:
    _obter_centro_ou_404(db, centro_custo_id)
    nota = NotaCentroCusto(centro_custo_id=centro_custo_id, usuario_id=usuario_atual.id, texto=dados.texto)
    db.add(nota)
    db.flush()
    auditoria_service.registrar_criacao(db, usuario_atual.id, "notas_centro_custo", nota)
    db.commit()
    db.refresh(nota)
    return NotaCentroCustoRead(
        id=nota.id,
        centro_custo_id=nota.centro_custo_id,
        usuario_id=nota.usuario_id,
        usuario_nome=usuario_atual.nome,
        texto=nota.texto,
        created_at=nota.created_at,
    )


@router.delete(
    "/notas/{nota_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_write_access)]
)
def excluir_nota(
    centro_custo_id: uuid.UUID,
    nota_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> None:
    """Quadro de notas é colaborativo — qualquer um com acesso de escrita
    pode apagar qualquer nota, não só a própria (mesmo nível de permissão
    de quem posta).
    """
    nota = (
        db.query(NotaCentroCusto)
        .filter(NotaCentroCusto.id == nota_id, NotaCentroCusto.centro_custo_id == centro_custo_id)
        .first()
    )
    if nota is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota não encontrada")
    auditoria_service.registrar_exclusao(db, usuario_atual.id, "notas_centro_custo", nota)
    db.delete(nota)
    db.commit()
