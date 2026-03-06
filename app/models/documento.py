from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.cliente import now_utc

if TYPE_CHECKING:
    from app.models.negocio import Negocio


class Documento(Base):
    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    negocio_id: Mapped[int] = mapped_column(ForeignKey("negocios.id", ondelete="CASCADE"), index=True)

    tipo: Mapped[str] = mapped_column(String(30))
    conteudo: Mapped[str] = mapped_column(Text)
    pdf_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    negocio: Mapped["Negocio"] = relationship(back_populates="documentos")
