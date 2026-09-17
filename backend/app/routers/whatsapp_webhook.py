"""Webhook público do WhatsApp (Meta Cloud API) — sem autenticação de usuário,
protegido por verify_token (handshake GET) e assinatura HMAC (POST)."""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.workers.tasks import processar_audio_whatsapp, processar_mensagem_whatsapp, processar_midia_nota_whatsapp

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
        # Fail-closed: sem app secret configurado não há como verificar que
        # a requisição veio mesmo da Meta — aceitar sem validar deixaria
        # qualquer POST não autenticado criar pré-lançamentos/notas fiscais.
        logger.error("WHATSAPP_APP_SECRET não configurado — recusando webhook por segurança")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Webhook do WhatsApp não está configurado com segurança"
        )
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
            # metadata.phone_number_id é o número QUE RECEBEU a mensagem — a
            # resposta precisa sair pelo mesmo número, nunca por um fixo,
            # já que o app pode ter mais de um número WhatsApp conectado.
            phone_number_id = valor.get("metadata", {}).get("phone_number_id")
            for mensagem in valor.get("messages", []):
                # cada mensagem é isolada: um campo inesperado numa mensagem
                # não pode derrubar a request com 500 e fazer a Meta reentregar
                # o payload inteiro (inclusive mensagens já processadas com
                # sucesso antes dela).
                try:
                    wamid = mensagem.get("id")
                    tipo = mensagem.get("type")
                    telefone = mensagem["from"]

                    if tipo == "text":
                        processar_mensagem_whatsapp.delay(telefone, mensagem["text"]["body"], phone_number_id, wamid)
                    elif tipo == "audio":
                        # voice note — transcreve e trata como se fosse texto
                        processar_audio_whatsapp.delay(telefone, mensagem["audio"]["id"], phone_number_id, wamid)
                    elif tipo in ("image", "document"):
                        # foto/PDF de nota fiscal — vira nota fiscal pendente de revisão
                        processar_midia_nota_whatsapp.delay(
                            telefone, mensagem[tipo]["id"], tipo, phone_number_id, wamid
                        )
                    else:
                        logger.info("Ignorando mensagem WhatsApp não suportada: %s", tipo)
                except Exception:
                    logger.exception("Falha ao processar item de mensagem WhatsApp: %r", mensagem)

    return {"status": "ok"}
