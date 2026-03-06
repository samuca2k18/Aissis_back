from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.negocio import Negocio


def now_utc():
    return datetime.now(timezone.utc)


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(200))
    telefone: Mapped[str] = mapped_column(String(50))
    cidade: Mapped[str] = mapped_column(String(120))
    cpf_cnpj: Mapped[str | None] = mapped_column(String(30), nullable=True)
    origem: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tipo_pessoa: Mapped[str] = mapped_column(String(20), default="fisica")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    negocios: Mapped[list["Negocio"]] = relationship(back_populates="cliente", cascade="all, delete-orphan")
    leads: Mapped[list["Lead"]] = relationship(back_populates="cliente", cascade="all, delete-orphan")
