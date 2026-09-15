from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models.enums import PapelUsuario
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.pre_lancamento_whatsapp import VincularTelefoneWhatsapp
from app.schemas.usuario import UsuarioCreate, UsuarioRead
from app.services.auth_service import criar_access_token, hash_senha, verificar_senha

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(dados: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if usuario is None or not usuario.ativo or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha inválidos")

    token = criar_access_token(usuario.id, usuario.papel)
    return TokenResponse(access_token=token, usuario=UsuarioRead.model_validate(usuario))


@router.get("/me", response_model=UsuarioRead)
def me(usuario_atual: Usuario = Depends(get_current_user)) -> Usuario:
    return usuario_atual


@router.patch("/me/telefone-whatsapp", response_model=UsuarioRead)
def vincular_telefone_whatsapp(
    dados: VincularTelefoneWhatsapp,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> Usuario:
    ja_vinculado = (
        db.query(Usuario)
        .filter(Usuario.telefone_whatsapp == dados.telefone_whatsapp, Usuario.id != usuario_atual.id)
        .first()
    )
    if ja_vinculado is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esse número já está vinculado a outro usuário")

    usuario_atual.telefone_whatsapp = dados.telefone_whatsapp
    db.commit()
    db.refresh(usuario_atual)
    return usuario_atual


@router.post(
    "/usuarios",
    response_model=UsuarioRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(PapelUsuario.admin, PapelUsuario.master))],
)
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
