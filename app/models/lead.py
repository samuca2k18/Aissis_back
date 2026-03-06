from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.cliente import now_utc

if TYPE_CHECKING:
    from app.models.cliente import Cliente


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
    nome: Mapped[str] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    origem: Mapped[str | None] = mapped_column(String(80), nullable=True)
    campanha: Mapped[str | None] = mapped_column(String(120), nullable=True)
    interesse: Mapped[str | None] = mapped_column(String(80), nullable=True)
    orcamento_estimado: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    temperatura: Mapped[str] = mapped_column(String(10), default="morno")
    status: Mapped[str] = mapped_column(String(30), default="novo")
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    cliente: Mapped["Cliente | None"] = relationship(back_populates="leads")
