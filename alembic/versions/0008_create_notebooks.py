"""create notebooks

Revision ID: 0008_create_notebooks
Revises: d0b2c0f348d7
Create Date: 2026-05-21 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_create_notebooks"
down_revision = "d0b2c0f348d7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notebooks",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("connector_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"]),
    )
    op.create_index("ix_notebooks_user_id", "notebooks", ["user_id"], unique=False)
    op.create_index("ix_notebooks_connector_id", "notebooks", ["connector_id"], unique=False)


def downgrade():
    op.drop_index("ix_notebooks_connector_id", table_name="notebooks")
    op.drop_index("ix_notebooks_user_id", table_name="notebooks")
    op.drop_table("notebooks")
