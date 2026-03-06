from datetime import datetime
from typing import Literal

from pydantic import BaseModel

CampanhaStatus = Literal["ativa", "pausada", "encerrada"]


class CampanhaCreate(BaseModel):
    nome: str
    plataforma: str
    investimento: float = 0.0
    leads_gerados: int = 0
    vendas: int = 0
    receita: float = 0.0
    status: CampanhaStatus = "ativa"
    data_inicio: datetime | None = None
    data_fim: datetime | None = None
    observacoes: str | None = None


class CampanhaUpdate(BaseModel):
    investimento: float | None = None
    leads_gerados: int | None = None
    vendas: int | None = None
    receita: float | None = None
    status: CampanhaStatus | None = None
    observacoes: str | None = None


class CampanhaOut(BaseModel):
    id: int
    nome: str
    plataforma: str
    investimento: float
    leads_gerados: int
    vendas: int
    receita: float
    status: str
    custo_por_lead: float | None = None
    roi_percentual: float | None = None
    data_inicio: datetime | None
    data_fim: datetime | None
    observacoes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}
