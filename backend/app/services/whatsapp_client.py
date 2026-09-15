"""Envio de mensagens via Meta Cloud API (WhatsApp Business oficial)."""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def enviar_mensagem_texto(telefone: str, texto: str) -> None:
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        logger.warning("WhatsApp não configurado (falta access_token/phone_number_id) — resposta não enviada")
        return

    url = f"{_GRAPH_API_BASE}/{settings.whatsapp_phone_number_id}/messages"
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
