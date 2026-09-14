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

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
