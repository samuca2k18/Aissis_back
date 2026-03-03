from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Numeric, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from .database import Base


def now_utc():
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────
#  CLIENTES
# ─────────────────────────────────────────
class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(200))
    telefone: Mapped[str] = mapped_column(String(50))
    cidade: Mapped[str] = mapped_column(String(120))
    cpf_cnpj: Mapped[str | None] = mapped_column(String(30), nullable=True)
    origem: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Pessoa física ou jurídica
    tipo_pessoa: Mapped[str] = mapped_column(String(20), default="fisica")  # fisica | juridica
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    negocios: Mapped[list["Negocio"]] = relationship(back_populates="cliente", cascade="all, delete-orphan")
    leads: Mapped[list["Lead"]] = relationship(back_populates="cliente", cascade="all, delete-orphan")


# ─────────────────────────────────────────
#  LEADS (funil de marketing)
# ─────────────────────────────────────────
class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
    nome: Mapped[str] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    origem: Mapped[str | None] = mapped_column(String(80), nullable=True)   # Instagram | Meta Ads | Indicação | Google | Site
    campanha: Mapped[str | None] = mapped_column(String(120), nullable=True)
    interesse: Mapped[str | None] = mapped_column(String(80), nullable=True)  # Compra | Locação | Manutenção
    orcamento_estimado: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    temperatura: Mapped[str] = mapped_column(String(10), default="morno")  # quente | morno | frio
    # novo | contatado | orçamento | negociacao | convertido | perdido
    status: Mapped[str] = mapped_column(String(30), default="novo")
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    cliente: Mapped["Cliente | None"] = relationship(back_populates="leads")


# ─────────────────────────────────────────
#  NEGÓCIOS
# ─────────────────────────────────────────
class Negocio(Base):
    __tablename__ = "negocios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), index=True)

    # venda | locacao | manutencao
    tipo: Mapped[str] = mapped_column(String(20))

    # novo | orcamento_enviado | negociacao | fechado | perdido
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


# ─────────────────────────────────────────
#  DOCUMENTOS
# ─────────────────────────────────────────
class Documento(Base):
    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    negocio_id: Mapped[int] = mapped_column(ForeignKey("negocios.id", ondelete="CASCADE"), index=True)

    # orcamento | contrato_locacao | recibo | proposta
    tipo: Mapped[str] = mapped_column(String(30))

    # Conteúdo texto (para exibição)
    conteudo: Mapped[str] = mapped_column(Text)

    # PDF em bytes (base64 via API)
    pdf_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    negocio: Mapped["Negocio"] = relationship(back_populates="documentos")


# ─────────────────────────────────────────
#  CAMPANHAS DE MARKETING
# ─────────────────────────────────────────
class Campanha(Base):
    __tablename__ = "campanhas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(200))
    plataforma: Mapped[str] = mapped_column(String(50))  # Meta | Google | Instagram | Outro
    investimento: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    leads_gerados: Mapped[int] = mapped_column(Integer, default=0)
    vendas: Mapped[int] = mapped_column(Integer, default=0)
    receita: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="ativa")  # ativa | pausada | encerrada
    data_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


# ─────────────────────────────────────────
#  AGENDA / EVENTOS
# ─────────────────────────────────────────
class Agenda(Base):
    __tablename__ = "agenda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # entrega | evento | manutencao | afinacao | followup | outro
    tipo: Mapped[str] = mapped_column(String(30), default="outro")
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True)
    negocio_id: Mapped[int | None] = mapped_column(ForeignKey("negocios.id", ondelete="SET NULL"), nullable=True)
    concluido: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
