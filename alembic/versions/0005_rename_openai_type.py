"""rename openai connection type

Revision ID: 0005_rename_openai_type
Revises: 0004_add_code_to_connectors
Create Date: 2026-05-20 00:00:00
"""

from alembic import op


revision = "0005_rename_openai_type"
down_revision = "0004_add_code_to_connectors"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE connectors SET connection_type = 'openai' WHERE connection_type = 'open-ai'")


def downgrade():
    op.execute("UPDATE connectors SET connection_type = 'open-ai' WHERE connection_type = 'openai'")
