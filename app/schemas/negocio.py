from datetime import datetime
from typing import Literal

from pydantic import BaseModel

NegocioTipo = Literal["venda", "locacao", "manutencao"]
NegocioStatus = Literal["novo", "orcamento_enviado", "negociacao", "fechado", "perdido"]


class NegocioCreate(BaseModel):
    cliente_id: int
    tipo: NegocioTipo
    valor: float | None = None
    data_evento: datetime | None = None
    data_entrega: datetime | None = None
    local_evento: str | None = None
    descricao_piano: str | None = None
    observacoes: str | None = None


class NegocioUpdateStatus(BaseModel):
    status: NegocioStatus


class NegocioOut(BaseModel):
    id: int
    cliente_id: int
    tipo: NegocioTipo
    status: NegocioStatus
    valor: float | None
    data_evento: datetime | None
    data_entrega: datetime | None
    local_evento: str | None
    descricao_piano: str | None
    observacoes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}
