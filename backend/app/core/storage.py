import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

_EXTENSOES_PDF = {".pdf"}
_EXTENSOES_EXTRATO = {".ofx", ".csv"}
_TAMANHO_MAXIMO_PADRAO = 15 * 1024 * 1024  # 15MB — generoso pra PDF de nota/boleto, contém extrato gigante


def salvar_bytes(
    conteudo: bytes,
    subpasta: str,
    nome_original: str,
    extensoes_permitidas: set[str] = _EXTENSOES_PDF,
    tamanho_maximo: int = _TAMANHO_MAXIMO_PADRAO,
) -> str:
    """Salva bytes já em mão (upload HTTP já lido, ou mídia baixada do
    WhatsApp) em storage/<subpasta>/ com nome único, e devolve o caminho
    relativo (usado em arquivo_pdf_path / boleto_arquivo_path /
    arquivo_original_path e servido depois via /storage).
    """
    extensao = Path(nome_original).suffix.lower()
    if extensao not in extensoes_permitidas:
        raise ValueError(
            f"tipo de arquivo não permitido: {extensao or 'sem extensão'} (permitido: {sorted(extensoes_permitidas)})"
        )

    if len(conteudo) > tamanho_maximo:
        raise ValueError(f"arquivo maior que o limite permitido ({tamanho_maximo // (1024 * 1024)}MB)")

    destino_dir = Path(settings.storage_dir) / subpasta
    destino_dir.mkdir(parents=True, exist_ok=True)

    nome_unico = f"{uuid.uuid4()}{extensao}"
    destino = destino_dir / nome_unico
    destino.write_bytes(conteudo)

    return f"{subpasta}/{nome_unico}"


def salvar_arquivo_upload(
    arquivo: UploadFile,
    subpasta: str,
    conteudo: bytes,
    extensoes_permitidas: set[str] = _EXTENSOES_PDF,
    tamanho_maximo: int = _TAMANHO_MAXIMO_PADRAO,
) -> str:
    return salvar_bytes(conteudo, subpasta, arquivo.filename or "", extensoes_permitidas, tamanho_maximo)
