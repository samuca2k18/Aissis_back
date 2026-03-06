from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.cliente import now_utc

if TYPE_CHECKING:
    from app.models.cliente import Cliente
    from app.models.documento import Documento


class Negocio(Base):
    __tablename__ = "negocios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), index=True)

    tipo: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="novo")
    valor: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    data_evento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    local_evento: Mapped[str | None] = mapped_column(String(300), nullable=True)
    descricao_piano: Mapped[str | None] = mapped_column(String(200), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    cliente: Mapped["Cliente"] = relationship(back_populates="negocios")
    documentos: Mapped[list["Documento"]] = relationship(back_populates="negocio", cascade="all, delete-orphan")
