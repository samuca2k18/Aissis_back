"""Modelo para rastrear o estado da conversa do WhatsApp por telefone."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.cliente import now_utc


class WhatsappSession(Base):
    __tablename__ = "whatsapp_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(30), unique=True, index=True)

    # Estado da máquina de estados:
    #   "menu"           → esperando escolher opção
    #   "orc_nome"       → coletando nome p/ orçamento
    #   "orc_telefone"   → coletando telefone
    #   "orc_cidade"     → coletando cidade
    #   "orc_itens"      → coletando itens (formato: descricao;valor, um por linha)
    #   "orc_pagamento"  → condição de pagamento
    #   "orc_confirmar"  → confirmação final
    #   "ag_titulo"      → coletando título do agendamento
    #   "ag_data"        → coletando data/hora do agendamento
    #   "ag_tipo"        → coletando tipo do agendamento
    #   "ag_confirmar"   → confirmação do agendamento
    state: Mapped[str] = mapped_column(String(30), default="menu")

    # Dados parciais coletados em formato JSON
    data_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="{}")

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
