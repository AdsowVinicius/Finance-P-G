"""Webhook público do WhatsApp (Meta Cloud API) — sem autenticação de usuário,
protegido por verify_token (handshake GET) e assinatura HMAC (POST)."""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.workers.tasks import processar_mensagem_whatsapp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])


@router.get("")
def verificar_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    if hub_mode != "subscribe" or hub_verify_token != settings.whatsapp_verify_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de verificação inválido")
    return PlainTextResponse(hub_challenge)


def _validar_assinatura(corpo: bytes, assinatura: str | None) -> None:
    if not settings.whatsapp_app_secret:
        return
    if assinatura is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assinatura ausente")
    esperado = "sha256=" + hmac.new(settings.whatsapp_app_secret.encode(), corpo, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(esperado, assinatura):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assinatura inválida")


@router.post("")
async def receber_mensagem(request: Request, x_hub_signature_256: str | None = Header(None)) -> dict[str, str]:
    corpo = await request.body()
    _validar_assinatura(corpo, x_hub_signature_256)
    payload = json.loads(corpo)

    for entrada in payload.get("entry", []):
        for mudanca in entrada.get("changes", []):
            valor = mudanca.get("value", {})
            for mensagem in valor.get("messages", []):
                if mensagem.get("type") != "text":
                    logger.info("Ignorando mensagem WhatsApp não-texto: %s", mensagem.get("type"))
                    continue
                telefone = mensagem["from"]
                texto = mensagem["text"]["body"]
                processar_mensagem_whatsapp.delay(telefone, texto)

    return {"status": "ok"}
