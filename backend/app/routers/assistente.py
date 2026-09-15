from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.schemas.assistente import PerguntaAssistente, RespostaAssistente
from app.services.assistente_consulta_service import AssistenteConsultaService, AssistenteIndisponivelError

router = APIRouter(prefix="/assistente", tags=["assistente"], dependencies=[Depends(get_current_user)])


@router.post("/perguntar", response_model=RespostaAssistente)
def perguntar(dados: PerguntaAssistente, db: Session = Depends(get_db)) -> RespostaAssistente:
    try:
        servico = AssistenteConsultaService()
    except AssistenteIndisponivelError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assistente indisponível: ANTHROPIC_API_KEY não configurada",
        ) from exc

    resposta = servico.responder(dados.pergunta, db)
    return RespostaAssistente(resposta=resposta)
