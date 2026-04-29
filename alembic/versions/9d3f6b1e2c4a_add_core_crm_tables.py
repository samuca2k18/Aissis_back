"""add core crm tables

Revision ID: 9d3f6b1e2c4a
Revises: 771b31870cbe
Create Date: 2026-04-29 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d3f6b1e2c4a"
down_revision: Union[str, None] = "771b31870cbe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campanhas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("plataforma", sa.String(length=50), nullable=False),
        sa.Column("investimento", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("leads_gerados", sa.Integer(), nullable=False),
        sa.Column("vendas", sa.Integer(), nullable=False),
        sa.Column("receita", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("data_inicio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_fim", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campanhas_id"), "campanhas", ["id"], unique=False)

    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("telefone", sa.String(length=50), nullable=False),
        sa.Column("cidade", sa.String(length=120), nullable=False),
        sa.Column("cpf_cnpj", sa.String(length=30), nullable=True),
        sa.Column("origem", sa.String(length=80), nullable=True),
        sa.Column("tipo_pessoa", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clientes_id"), "clientes", ["id"], unique=False)

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("telefone", sa.String(length=50), nullable=True),
        sa.Column("origem", sa.String(length=80), nullable=True),
        sa.Column("campanha", sa.String(length=120), nullable=True),
        sa.Column("interesse", sa.String(length=80), nullable=True),
        sa.Column("orcamento_estimado", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("temperatura", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_leads_id"), "leads", ["id"], unique=False)

    op.create_table(
        "negocios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("valor", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("data_evento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_entrega", sa.DateTime(timezone=True), nullable=True),
        sa.Column("local_evento", sa.String(length=300), nullable=True),
        sa.Column("descricao_piano", sa.String(length=200), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_negocios_id"), "negocios", ["id"], unique=False)
    op.create_index(op.f("ix_negocios_cliente_id"), "negocios", ["cliente_id"], unique=False)

    op.create_table(
        "agenda",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("data_hora", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("negocio_id", sa.Integer(), nullable=True),
        sa.Column("concluido", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["negocio_id"], ["negocios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agenda_id"), "agenda", ["id"], unique=False)

    op.create_table(
        "documentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("negocio_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("conteudo", sa.Text(), nullable=False),
        sa.Column("pdf_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["negocio_id"], ["negocios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documentos_id"), "documentos", ["id"], unique=False)
    op.create_index(op.f("ix_documentos_negocio_id"), "documentos", ["negocio_id"], unique=False)

    op.create_table(
        "whatsapp_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_whatsapp_sessions_id"), "whatsapp_sessions", ["id"], unique=False)
    op.create_index(op.f("ix_whatsapp_sessions_phone"), "whatsapp_sessions", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_whatsapp_sessions_phone"), table_name="whatsapp_sessions")
    op.drop_index(op.f("ix_whatsapp_sessions_id"), table_name="whatsapp_sessions")
    op.drop_table("whatsapp_sessions")

    op.drop_index(op.f("ix_documentos_negocio_id"), table_name="documentos")
    op.drop_index(op.f("ix_documentos_id"), table_name="documentos")
    op.drop_table("documentos")

    op.drop_index(op.f("ix_agenda_id"), table_name="agenda")
    op.drop_table("agenda")

    op.drop_index(op.f("ix_negocios_cliente_id"), table_name="negocios")
    op.drop_index(op.f("ix_negocios_id"), table_name="negocios")
    op.drop_table("negocios")

    op.drop_index(op.f("ix_leads_id"), table_name="leads")
    op.drop_table("leads")

    op.drop_index(op.f("ix_clientes_id"), table_name="clientes")
    op.drop_table("clientes")

    op.drop_index(op.f("ix_campanhas_id"), table_name="campanhas")
    op.drop_table("campanhas")
