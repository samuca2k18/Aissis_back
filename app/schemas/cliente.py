from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ClienteCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    telefone: str = Field(min_length=6, max_length=50)
    cidade: str = Field(min_length=2, max_length=120)
    cpf_cnpj: str | None = Field(default=None, max_length=30)
    origem: str | None = Field(default=None, max_length=80)
    tipo_pessoa: Literal["fisica", "juridica"] = "fisica"


class ClienteUpdate(BaseModel):
    nome: str | None = None
    telefone: str | None = None
    cidade: str | None = None
    cpf_cnpj: str | None = None
    origem: str | None = None


class ClienteOut(BaseModel):
    id: int
    nome: str
    telefone: str
    cidade: str
    cpf_cnpj: str | None
    origem: str | None
    tipo_pessoa: str
    created_at: datetime
    model_config = {"from_attributes": True}
