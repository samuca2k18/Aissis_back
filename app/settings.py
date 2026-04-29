from typing import Final

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    APP_NAME: str = "IAssis Pianos"
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    DATABASE_STATEMENT_TIMEOUT_MS: int = 30000
    AUTO_CREATE_TABLES: bool = False
    SCHEDULER_ENABLED: bool = True
    AUDIT_LOG_ENABLED: bool = True

    COMPANY_NAME: str = "JR NASCIMENTOS VENDA E CONSERTO DE INSTRUMENTOS MUSICAIS LTDA."
    COMPANY_CNPJ: str = "09.481.301/0001-59"
    COMPANY_CNPJ_CONTRATO: str = "09.481.301/0002-30"
    COMPANY_CPF_SOCIO: str = "408.321.983-15"
    COMPANY_ADDRESS: str = "Av. Rui Barbosa, 780 lj.10 – Meireles – Fortaleza – CE"
    COMPANY_PHONE: str = "(85) 3067-1283 / 99622-4480"
    COMPANY_EMAIL: str = "otpianos@yahoo.com.br / assispianos@hotmail.com"
    COMPANY_RESPONSAVEL: str = "Francisco de Assis do Nascimento Jr."

    DEFAULT_BUDGET_VALID_DAYS: int = 7

    # Evolution API (WhatsApp)
    EVOLUTION_API_URL: str = ""
    EVOLUTION_API_KEY: str = ""
    EVOLUTION_API_INSTANCE: str = ""
    EVOLUTION_API_TIMEOUT_SECONDS: float = 10.0
    WHATSAPP_WEBHOOK_TOKEN: str = ""
    WHATSAPP_LID_MAP_JSON: str = ""

    # Telefone que recebe o resumo diário às 7h (formato: 5585999999999)
    WHATSAPP_NOTIFY_PHONE: str = ""
    BACKEND_API_KEY: str = ""
    CORS_ALLOW_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    CORS_ALLOW_CREDENTIALS: bool = False
    AUTH_REQUIRED: bool = True
    AUTH_SECRET_KEY: str = "change-me-in-production"
    AUTH_BOOTSTRAP_TOKEN: str = ""
    AUTH_TOKEN_EXPIRE_MINUTES: int = 480
    AUTH_PASSWORD_ITERATIONS: int = 390000
    AUTH_BOOTSTRAP_ADMIN: bool = True
    INITIAL_ADMIN_NAME: str = "Administrador"
    INITIAL_ADMIN_EMAIL: str = ""
    INITIAL_ADMIN_PASSWORD: str = ""

    _ORIGINS_SEPARATOR: Final[str] = ","

    @property
    def cors_allow_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.CORS_ALLOW_ORIGINS.split(self._ORIGINS_SEPARATOR) if origin.strip()]
        if not origins:
            return ["http://localhost:5173"]
        return origins

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in {"prod", "production"}


settings = Settings()
