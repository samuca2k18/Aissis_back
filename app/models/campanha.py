from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.cliente import now_utc


class Campanha(Base):
    __tablename__ = "campanhas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(200))
    plataforma: Mapped[str] = mapped_column(String(50))
    investimento: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    leads_gerados: Mapped[int] = mapped_column(Integer, default=0)
    vendas: Mapped[int] = mapped_column(Integer, default=0)
    receita: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="ativa")
    data_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
