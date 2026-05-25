"""make active the notebook default

Revision ID: 0011_active_notebook_default
Revises: 0010_notebook_embedding_config
Create Date: 2026-05-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_active_notebook_default"
down_revision = "0010_notebook_embedding_config"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE notebooks SET status = 'active' WHERE status = 'pending' AND embedding_config_id IS NOT NULL")
    op.alter_column(
        "notebooks",
        "status",
        existing_type=sa.String(length=50),
        server_default="active",
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "notebooks",
        "status",
        existing_type=sa.String(length=50),
        server_default="pending",
        existing_nullable=False,
    )
