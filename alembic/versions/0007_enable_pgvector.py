"""enable pgvector extension

Revision ID: 0007_enable_pgvector
Revises: 0006_add_connector_embeddings
Create Date: 2026-05-21 00:00:00
"""

from alembic import op


revision = "0007_enable_pgvector"
down_revision = "0006_add_connector_embeddings"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade():
    op.execute("DROP EXTENSION IF EXISTS vector")
