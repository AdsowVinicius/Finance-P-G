"""Envio de mensagens via Meta Cloud API (WhatsApp Business oficial)."""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_GRAPH_API_BASE = "https://graph.facebook.com/v25.0"


def enviar_mensagem_texto(telefone: str, texto: str, phone_number_id: str | None = None) -> None:
    """phone_number_id: o número QUE RECEBEU a mensagem original (vem do
    webhook) — a resposta tem que sair por esse mesmo número. Cai pro
    settings.whatsapp_phone_number_id só se o webhook não informar nenhum
    (ex.: chamada manual/teste)."""
    numero_envio = phone_number_id or settings.whatsapp_phone_number_id
    if not settings.whatsapp_access_token or not numero_envio:
        logger.warning("WhatsApp não configurado (falta access_token/phone_number_id) — resposta não enviada")
        return

    url = f"{_GRAPH_API_BASE}/{numero_envio}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": texto[:4096]},
    }
    with httpx.Client(timeout=10) as client:
        resposta = client.post(url, headers=headers, json=payload)
        if resposta.status_code >= 400:
            logger.error("Falha ao enviar mensagem WhatsApp para %s: %s", telefone, resposta.text)


def baixar_midia(media_id: str) -> tuple[bytes, str]:
    """Baixa uma mídia (áudio, imagem, documento) recebida via webhook —
    dois passos: resolve a URL temporária assinada da mídia, depois baixa
    o conteúdo (os dois passos exigem o Bearer token). Devolve (bytes, mime_type).
    """
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    with httpx.Client(timeout=30) as client:
        resposta_info = client.get(f"{_GRAPH_API_BASE}/{media_id}", headers=headers)
        resposta_info.raise_for_status()
        info = resposta_info.json()

        resposta_arquivo = client.get(info["url"], headers=headers)
        resposta_arquivo.raise_for_status()
        return resposta_arquivo.content, info["mime_type"]
