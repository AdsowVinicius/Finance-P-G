import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models.enums import PapelUsuario
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioRead, UsuarioUpdate
from app.services.auth_service import hash_senha

router = APIRouter(
    prefix="/usuarios",
    tags=["usuarios"],
    dependencies=[Depends(get_current_user), Depends(require_roles(PapelUsuario.admin, PapelUsuario.master))],
)


@router.get("", response_model=list[UsuarioRead])
def listar_usuarios(db: Session = Depends(get_db)) -> list[Usuario]:
    return db.query(Usuario).order_by(Usuario.nome).all()


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def criar_usuario(dados: UsuarioCreate, db: Session = Depends(get_db)) -> Usuario:
    if db.query(Usuario).filter(Usuario.email == dados.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe um usuário com este email")

    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        papel=dados.papel,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch("/{usuario_id}", response_model=UsuarioRead)
def atualizar_usuario(usuario_id: uuid.UUID, dados: UsuarioUpdate, db: Session = Depends(get_db)) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    if dados.nome is not None:
        usuario.nome = dados.nome
    if dados.papel is not None:
        usuario.papel = dados.papel
    if dados.ativo is not None:
        usuario.ativo = dados.ativo
    if dados.senha:
        usuario.senha_hash = hash_senha(dados.senha)

    db.commit()
    db.refresh(usuario)
    return usuario
