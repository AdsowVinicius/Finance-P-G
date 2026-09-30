from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://pgfinance:pgfinance@localhost:5432/pgfinance"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    jwt_secret_key: str = "troque-isso-por-um-valor-aleatorio-forte"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480

    cors_origins: str = "http://localhost:5173"

    storage_dir: str = "./storage"

    # Consulta de NFe (opção 3, sem certificado digital) — provedor Meu Danfe
    # (api.meudanfe.com.br), R$0,03/consulta. Ver NfeConsultaClient.
    # Sem chave configurada, o pipeline fica só na extração de chave (sem API externa).
    meudanfe_api_key: str | None = None
    meudanfe_base_url: str = "https://api.meudanfe.com.br/v2"

    # RF16 — assistente de consulta em linguagem natural (Claude Haiku 4.5).
    # Sem chave configurada, o endpoint do assistente responde 503.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5"

    # WhatsApp (roadmap) — Meta Cloud API oficial. Reaproveita o motor do
    # RF16 (mesma chave ANTHROPIC_API_KEY acima) + funções de escrita.
    # Sem whatsapp_access_token/phone_number_id, o envio de resposta é pulado.
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_app_secret: str | None = None

    # Transcrição de áudio do WhatsApp — Whisper local (faster-whisper),
    # sem API paga externa. Tamanhos: tiny/base/small/medium/large-v3 — small
    # é o equilíbrio padrão entre velocidade (CPU) e qualidade em português.
    whisper_model_size: str = "small"

    # Certificado digital A1 (roadmap -> ativado). O .pfx e a senha ficam no
    # banco CIFRADOS com Fernet; a chave vem só daqui. Gere com:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Perder esta chave = reenviar o certificado (ele não é recuperável).
    cert_encryption_key: str | None = None

    # SEFAZ — NFeDistribuicaoDFe (Ambiente Nacional). "producao" | "homologacao".
    sefaz_ambiente: str = "producao"
    # Verificação TLS sempre ligada. No Windows o Python usa o repositório de
    # certificados do sistema (onde a AC Raiz ICP-Brasil costuma estar); se a
    # verificação falhar, aponte um .pem com a cadeia da SEFAZ aqui.
    sefaz_ca_bundle: str | None = None

    # Open Finance via Pluggy (agregador). Sem client_id/secret o módulo
    # responde 503. Credenciais em https://dashboard.pluggy.ai
    pluggy_client_id: str | None = None
    pluggy_client_secret: str | None = None
    pluggy_base_url: str = "https://api.pluggy.ai"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
