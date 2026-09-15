import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import PapelUsuario
from app.models.usuario import Usuario
from app.services.auth_service import decodificar_access_token

_bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    credenciais_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decodificar_access_token(credentials.credentials)
        usuario_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise credenciais_invalidas from exc

    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise credenciais_invalidas
    return usuario


def require_roles(*papeis_permitidos: PapelUsuario) -> Callable[[Usuario], Usuario]:
    def dependency(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.papel not in papeis_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para executar esta ação",
            )
        return usuario

    return dependency


# Cadastros base (parceiros, centros de custo, contas bancárias) e lançamentos
# financeiros podem ser escritos por financeiro/admin/master; "sub" só lê.
require_write_access = require_roles(PapelUsuario.financeiro, PapelUsuario.admin, PapelUsuario.master)

# Exclusão definitiva (irreversível, sem histórico de dado) é mais restrita
# que escrita normal — só admin/master, nunca financeiro.
require_admin = require_roles(PapelUsuario.admin, PapelUsuario.master)
