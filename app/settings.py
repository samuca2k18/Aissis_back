from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    APP_NAME: str = "IAssis Pianos"

    COMPANY_NAME: str = "JR NASCIMENTOS VENDA E CONSERTO DE INSTRUMENTOS MUSICAIS LTDA."
    COMPANY_CNPJ: str = "09.481.301/0001-59"
    COMPANY_CNPJ_CONTRATO: str = "09.481.301/0002-30"
    COMPANY_CPF_SOCIO: str = "408.321.983-15"
    COMPANY_ADDRESS: str = "Av. Rui Barbosa, 780 lj.10 – Meireles – Fortaleza – CE"
    COMPANY_PHONE: str = "(85) 3067-1283 / 99622-4480"
    COMPANY_EMAIL: str = "otpianos@yahoo.com.br / assispianos@hotmail.com"
    COMPANY_RESPONSAVEL: str = "Francisco de Assis do Nascimento Jr."

    DEFAULT_BUDGET_VALID_DAYS: int = 7


settings = Settings()
