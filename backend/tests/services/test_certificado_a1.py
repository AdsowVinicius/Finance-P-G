from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from app.config import settings
from app.services import certificado_a1_service, criptografia_service
from app.services.certificado_a1_service import CertificadoInvalido

CNPJ = "12345678000199"


def _gerar_pfx(senha: str = "segredo", cn: str = f"P&G ENGENHARIA LTDA:{CNPJ}", dias_validade: int = 365, inicio_dias: int = -1) -> bytes:
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    agora = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora + timedelta(days=inicio_dias))
        .not_valid_after(agora + timedelta(days=dias_validade))
        .sign(chave, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        b"teste", chave, cert, None, serialization.BestAvailableEncryption(senha.encode())
    )


def test_le_cnpj_razao_e_validade_do_certificado():
    info, _ = certificado_a1_service.carregar(_gerar_pfx(), "segredo")
    assert info.cnpj == CNPJ
    assert info.razao_social == "P&G ENGENHARIA LTDA"
    assert info.valido_ate > datetime.now(timezone.utc)
    assert len(info.fingerprint_sha256) == 64


def test_senha_errada_vira_certificado_invalido():
    with pytest.raises(CertificadoInvalido, match="senha"):
        certificado_a1_service.carregar(_gerar_pfx(), "errada")


def test_arquivo_que_nao_e_pfx_e_rejeitado():
    with pytest.raises(CertificadoInvalido):
        certificado_a1_service.carregar(b"isso nao e um pfx", "x")


def test_certificado_vencido_e_rejeitado():
    with pytest.raises(CertificadoInvalido, match="vencido"):
        certificado_a1_service.carregar(_gerar_pfx(dias_validade=-1, inicio_dias=-10), "segredo")


def test_certificado_sem_cnpj_e_rejeitado():
    with pytest.raises(CertificadoInvalido, match="CNPJ"):
        certificado_a1_service.carregar(_gerar_pfx(cn="Fulano de Tal"), "segredo")


def test_fingerprint_e_estavel_para_o_mesmo_certificado():
    pfx = _gerar_pfx()
    a, _ = certificado_a1_service.carregar(pfx, "segredo")
    b, _ = certificado_a1_service.carregar(pfx, "segredo")
    assert a.fingerprint_sha256 == b.fingerprint_sha256


def test_contexto_mtls_carrega_e_nao_deixa_pem_em_disco(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    with certificado_a1_service.contexto_mtls(_gerar_pfx(), "segredo") as ctx:
        assert ctx is not None
    assert list(tmp_path.iterdir()) == []


def test_criptografia_ida_e_volta(monkeypatch):
    monkeypatch.setattr(settings, "cert_encryption_key", Fernet.generate_key().decode())
    cifrado = criptografia_service.cifrar(b"pfx-bytes")
    assert cifrado != b"pfx-bytes"
    assert criptografia_service.decifrar(cifrado) == b"pfx-bytes"


def test_criptografia_sem_chave_levanta(monkeypatch):
    monkeypatch.setattr(settings, "cert_encryption_key", None)
    with pytest.raises(criptografia_service.CriptografiaNaoConfigurada):
        criptografia_service.cifrar(b"x")


def test_decifrar_com_outra_chave_levanta(monkeypatch):
    monkeypatch.setattr(settings, "cert_encryption_key", Fernet.generate_key().decode())
    cifrado = criptografia_service.cifrar(b"x")
    monkeypatch.setattr(settings, "cert_encryption_key", Fernet.generate_key().decode())
    with pytest.raises(criptografia_service.CriptografiaInvalida):
        criptografia_service.decifrar(cifrado)
