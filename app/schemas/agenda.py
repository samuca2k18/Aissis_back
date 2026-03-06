from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AgendaCreate(BaseModel):
    titulo: str
    descricao: str | None = None
    data_hora: datetime
    tipo: Literal["entrega", "evento", "manutencao", "afinacao", "followup", "outro"] = "outro"
    cliente_id: int | None = None
    negocio_id: int | None = None


class AgendaOut(BaseModel):
    id: int
    titulo: str
    descricao: str | None
    data_hora: datetime
    tipo: str
    cliente_id: int | None
    negocio_id: int | None
    concluido: bool
    created_at: datetime
    model_config = {"from_attributes": True}
