import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import PapelUsuario


class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    # max_length=72: limite do próprio bcrypt — sem isso, uma senha maior
    # derruba o hash com erro 500 em vez de uma validação 422 limpa.
    senha: str = Field(min_length=8, max_length=72)
    papel: PapelUsuario = PapelUsuario.sub


class UsuarioUpdate(BaseModel):
    nome: str | None = None
    papel: PapelUsuario | None = None
    ativo: bool | None = None
    senha: str | None = Field(default=None, min_length=8, max_length=72)


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    email: EmailStr
    papel: PapelUsuario
    ativo: bool
    telefone_whatsapp: str | None = None
