"""create connectors

Revision ID: 0003_create_connectors
Revises: 0002_add_role_to_users
Create Date: 2026-05-19 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_create_connectors"
down_revision = "0002_add_role_to_users"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "connectors",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("connection_type", sa.String(length=50), nullable=False),
        sa.Column("local_file_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_connectors_user_id", "connectors", ["user_id"], unique=False)


def downgrade():
    op.drop_index("ix_connectors_user_id", table_name="connectors")
    op.drop_table("connectors")
