from pydantic import BaseModel, Field


class PerguntaAssistente(BaseModel):
    pergunta: str = Field(min_length=1, max_length=500)


class RespostaAssistente(BaseModel):
    resposta: str
