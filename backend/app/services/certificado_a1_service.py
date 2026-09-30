"""Leitura e validação de certificado digital A1 (.pfx/.p12, ICP-Brasil).

Só lida com o arquivo em si (parse, CNPJ, validade, contexto mTLS) — não
sabe de banco nem de SEFAZ. Erros de certificado são `CertificadoInvalido`
com mensagem pronta pro usuário.
"""

import hashlib
import re
import shutil
import ssl
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import NamedTuple
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

# OID ICP-Brasil do CNPJ da pessoa jurídica (otherName no SubjectAltName)
_OID_CNPJ_ICP = x509.ObjectIdentifier("2.16.76.1.3.3")
_TAMANHO_MAXIMO_PFX = 512 * 1024


class CertificadoInvalido(Exception):
    pass


@dataclass
class CertificadoInfo:
    cnpj: str
    razao_social: str
    valido_de: datetime
    valido_ate: datetime
    fingerprint_sha256: str


def _extrair_cnpj(cert: x509.Certificate) -> str | None:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        for nome in san:
            if isinstance(nome, x509.OtherName) and nome.type_id == _OID_CNPJ_ICP:
                achado = re.search(rb"\d{14}", nome.value)
                if achado:
                    return achado.group().decode()
    except x509.ExtensionNotFound:
        pass

    # fallback: ICP-Brasil costuma por "RAZAO SOCIAL:12345678000199" no CN
    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if cn:
        achado = re.search(r"(?<!\d)\d{14}(?!\d)", str(cn[0].value))
        if achado:
            return achado.group()
    return None


def _razao_social(cert: x509.Certificate) -> str:
    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    texto = str(cn[0].value) if cn else ""
    return texto.split(":")[0].strip() or texto


class MaterialA1(NamedTuple):
    key: object
    cert: x509.Certificate


def carregar(pfx: bytes, senha: str) -> tuple[CertificadoInfo, MaterialA1]:
    if len(pfx) > _TAMANHO_MAXIMO_PFX:
        raise CertificadoInvalido("arquivo grande demais pra ser um certificado A1")
    try:
        chave, cert, _ = pkcs12.load_key_and_certificates(pfx, senha.encode("utf-8"))
    except ValueError as exc:
        # senha errada, arquivo não-PFX ou PFX legado (RC2-40) sem suporte do OpenSSL 3
        raise CertificadoInvalido(
            "não foi possível abrir o certificado: confira a senha e se o arquivo é um .pfx/.p12 A1. "
            "Certificados antigos (cifra RC2) precisam ser reexportados com `openssl pkcs12 -legacy` "
            "ou pelo gerenciador de certificados do Windows (AES-256)."
        ) from exc
    if chave is None or cert is None:
        raise CertificadoInvalido("o arquivo não contém chave privada e certificado")

    cnpj = _extrair_cnpj(cert)
    if cnpj is None:
        raise CertificadoInvalido("não achei o CNPJ no certificado (precisa ser e-CNPJ A1 de pessoa jurídica)")

    agora = datetime.now(timezone.utc)
    valido_de = cert.not_valid_before_utc
    valido_ate = cert.not_valid_after_utc
    if agora >= valido_ate:
        raise CertificadoInvalido(f"certificado vencido em {valido_ate:%d/%m/%Y}")
    if agora < valido_de:
        raise CertificadoInvalido(f"certificado só vale a partir de {valido_de:%d/%m/%Y}")

    info = CertificadoInfo(
        cnpj=cnpj,
        razao_social=_razao_social(cert),
        valido_de=valido_de,
        valido_ate=valido_ate,
        fingerprint_sha256=hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest(),
    )
    return info, MaterialA1(chave, cert)


@contextmanager
def contexto_mtls(pfx: bytes, senha: str, ca_bundle: str | None = None):
    """Contexto SSL com o certificado de cliente (mTLS). O módulo ssl só
    carrega de arquivo, então o PEM existe em disco por instantes num
    diretório temporário e é apagado assim que o contexto carrega — o
    SSLContext guarda o material em memória, não precisa mais do arquivo.
    """
    _, material = carregar(pfx, senha)
    pem = material.key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ) + material.cert.public_bytes(serialization.Encoding.PEM)

    contexto = ssl.create_default_context(cafile=ca_bundle)
    pasta = Path(tempfile.mkdtemp(prefix="a1-"))
    try:
        arquivo = pasta / "cliente.pem"
        arquivo.write_bytes(pem)
        contexto.load_cert_chain(certfile=str(arquivo))
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    yield contexto
