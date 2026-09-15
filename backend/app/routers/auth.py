from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.pre_lancamento_whatsapp import VincularTelefoneWhatsapp
from app.schemas.usuario import UsuarioRead
from app.services.auth_service import criar_access_token, verificar_senha

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
