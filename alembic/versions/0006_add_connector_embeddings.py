"""add embedding fields to connectors

Revision ID: 0006_add_connector_embeddings
Revises: 0005_rename_openai_type
Create Date: 2026-05-21 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_add_connector_embeddings"
down_revision = "0005_rename_openai_type"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("connectors", sa.Column("embedding_local_file_path", sa.String(length=1024), nullable=True))
    op.add_column("connectors", sa.Column("embedding_name", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("connectors", "embedding_name")
    op.drop_column("connectors", "embedding_local_file_path")
