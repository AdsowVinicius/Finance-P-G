"""Cadastro do certificado A1 no banco (cifrado) e ciclo de vida.

`cadastrar` valida o .pfx antes de gravar, cifra arquivo+senha e garante um
único certificado ativo (o anterior é desativado — o histórico fica). Devolve
Result object em vez de levantar exceção pra erro esperado (senha errada,
vencido, duplicado).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.certificado_digital import CertificadoDigital
from app.services import certificado_a1_service, criptografia_service
from app.services.certificado_a1_service import CertificadoInvalido

DIAS_ALERTA_VENCIMENTO = 30


@dataclass
class ResultadoCadastroCertificado:
    ok: bool
    certificado: CertificadoDigital | None = None
    codigo_erro: str | None = None  # "invalido" | "duplicado" | "criptografia_nao_configurada"
    erro: str | None = None


def cadastrar(
    db: Session, *, pfx: bytes, senha: str, criado_por: uuid.UUID, uf_autor: int = 35
) -> ResultadoCadastroCertificado:
    try:
        info, _ = certificado_a1_service.carregar(pfx, senha)
    except CertificadoInvalido as exc:
        return ResultadoCadastroCertificado(ok=False, codigo_erro="invalido", erro=str(exc))

    duplicado = db.query(CertificadoDigital).filter(CertificadoDigital.fingerprint_sha256 == info.fingerprint_sha256).first()
    if duplicado is not None:
        return ResultadoCadastroCertificado(
            ok=False, codigo_erro="duplicado", erro="Este certificado já foi cadastrado anteriormente"
        )

    try:
        arquivo_cifrado = criptografia_service.cifrar(pfx)
        senha_cifrada = criptografia_service.cifrar(senha.encode("utf-8"))
    except criptografia_service.CriptografiaNaoConfigurada as exc:
        return ResultadoCadastroCertificado(ok=False, codigo_erro="criptografia_nao_configurada", erro=str(exc))

    # no máximo 1 ativo (índice parcial no banco também garante)
    for anterior in db.query(CertificadoDigital).filter(CertificadoDigital.ativo.is_(True)).all():
        anterior.ativo = False
    db.flush()

    certificado = CertificadoDigital(
        cnpj=info.cnpj,
        razao_social=info.razao_social,
        arquivo_cifrado=arquivo_cifrado,
        senha_cifrada=senha_cifrada,
        fingerprint_sha256=info.fingerprint_sha256,
        valido_de=info.valido_de,
        valido_ate=info.valido_ate,
        uf_autor=uf_autor,
        criado_por=criado_por,
    )
    db.add(certificado)
    db.flush()
    return ResultadoCadastroCertificado(ok=True, certificado=certificado)


def obter_ativo(db: Session) -> CertificadoDigital | None:
    return db.query(CertificadoDigital).filter(CertificadoDigital.ativo.is_(True)).first()


def abrir(certificado: CertificadoDigital) -> tuple[bytes, str]:
    """Decifra (pfx, senha). Só chamar no momento de usar."""
    pfx = criptografia_service.decifrar(bytes(certificado.arquivo_cifrado))
    senha = criptografia_service.decifrar(bytes(certificado.senha_cifrada)).decode("utf-8")
    return pfx, senha


def dias_para_vencer(certificado: CertificadoDigital) -> int:
    return (certificado.valido_ate - datetime.now(timezone.utc)).days


def vencendo_em_breve(certificado: CertificadoDigital) -> bool:
    return certificado.valido_ate - datetime.now(timezone.utc) <= timedelta(days=DIAS_ALERTA_VENCIMENTO)
