"""add webhook messages table

Revision ID: 4b5fa5ddad7e
Revises: 
Create Date: 2026-03-31 02:32:03.399301

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b5fa5ddad7e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_webhook_messages_id"), "webhook_messages", ["id"], unique=False)
    op.create_index(op.f("ix_webhook_messages_message_id"), "webhook_messages", ["message_id"], unique=True)
    op.create_index(op.f("ix_webhook_messages_phone"), "webhook_messages", ["phone"], unique=False)
    op.create_index(op.f("ix_webhook_messages_received_at"), "webhook_messages", ["received_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_webhook_messages_received_at"), table_name="webhook_messages")
    op.drop_index(op.f("ix_webhook_messages_phone"), table_name="webhook_messages")
    op.drop_index(op.f("ix_webhook_messages_message_id"), table_name="webhook_messages")
    op.drop_index(op.f("ix_webhook_messages_id"), table_name="webhook_messages")
    op.drop_table("webhook_messages")
