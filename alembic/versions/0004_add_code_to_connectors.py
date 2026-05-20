"""add code to connectors

Revision ID: 0004_add_code_to_connectors
Revises: 0003_create_connectors
Create Date: 2026-05-20 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_code_to_connectors"
down_revision = "0003_create_connectors"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("connectors", sa.Column("code", sa.String(length=100), nullable=True))
    op.execute("UPDATE connectors SET code = id WHERE code IS NULL")
    op.alter_column("connectors", "code", existing_type=sa.String(length=100), nullable=False)
    op.create_unique_constraint("uq_connectors_user_id_code", "connectors", ["user_id", "code"])


def downgrade():
    op.drop_constraint("uq_connectors_user_id_code", "connectors", type_="unique")
    op.drop_column("connectors", "code")
