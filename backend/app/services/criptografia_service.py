"""Criptografia em repouso (Fernet) pro certificado A1 e sua senha.

A chave vem de CERT_ENCRYPTION_KEY, nunca do banco nem do JWT_SECRET_KEY
(comprometer um não pode comprometer o outro).
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class CriptografiaNaoConfigurada(Exception):
    pass


class CriptografiaInvalida(Exception):
    """Token adulterado ou cifrado com outra chave."""


def _fernet() -> Fernet:
    if not settings.cert_encryption_key:
        raise CriptografiaNaoConfigurada("CERT_ENCRYPTION_KEY não configurada")
    try:
        return Fernet(settings.cert_encryption_key.encode())
    except (ValueError, TypeError) as exc:
        raise CriptografiaNaoConfigurada("CERT_ENCRYPTION_KEY inválida (precisa ser uma chave Fernet)") from exc


def cifrar(dados: bytes) -> bytes:
    return _fernet().encrypt(dados)


def decifrar(dados: bytes) -> bytes:
    try:
        return _fernet().decrypt(dados)
    except InvalidToken as exc:
        raise CriptografiaInvalida("não foi possível decifrar (chave diferente da usada no cadastro?)") from exc
