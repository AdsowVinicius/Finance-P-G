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

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
