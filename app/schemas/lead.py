from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

LeadStatus = Literal["novo", "contatado", "orcamento", "negociacao", "convertido", "perdido"]
Temperatura = Literal["quente", "morno", "frio"]


class LeadCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    telefone: str | None = None
    origem: str | None = None
    campanha: str | None = None
    interesse: str | None = None
    orcamento_estimado: float | None = None
    temperatura: Temperatura = "morno"
    observacoes: str | None = None
    cliente_id: int | None = None


class LeadUpdateStatus(BaseModel):
    status: LeadStatus
    temperatura: Temperatura | None = None


class LeadOut(BaseModel):
    id: int
    cliente_id: int | None
    nome: str
    telefone: str | None
    origem: str | None
    campanha: str | None
    interesse: str | None
    orcamento_estimado: float | None
    temperatura: str
    status: str
    observacoes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}
