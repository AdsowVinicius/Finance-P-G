from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_master
from app.database import get_db
from app.models.categoria_lancamento import CategoriaLancamento
from app.models.usuario import Usuario
from app.schemas.categoria_lancamento import CategoriaLancamentoCreate, CategoriaLancamentoRead
from app.services import auditoria_service

router = APIRouter(prefix="/categorias-lancamento", tags=["categorias de lançamento"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CategoriaLancamentoRead])
def listar_categorias(apenas_ativas: bool = True, db: Session = Depends(get_db)) -> list[CategoriaLancamento]:
    query = db.query(CategoriaLancamento)
    if apenas_ativas:
        query = query.filter(CategoriaLancamento.ativo.is_(True))
    return query.order_by(CategoriaLancamento.nome).all()


@router.post(
    "", response_model=CategoriaLancamentoRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_master)]
)
def criar_categoria(
    dados: CategoriaLancamentoCreate, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> CategoriaLancamento:
    categoria = CategoriaLancamento(**dados.model_dump())
    db.add(categoria)
    db.flush()
    auditoria_service.registrar_criacao(db, usuario_atual.id, "categorias_lancamento", categoria)
    db.commit()
    db.refresh(categoria)
    return categoria
