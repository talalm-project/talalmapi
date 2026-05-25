"""add embedding config to notebooks

Revision ID: 0010_notebook_embedding_config
Revises: 0009_embedding_vectors
Create Date: 2026-05-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_notebook_embedding_config"
down_revision = "0009_embedding_vectors"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notebooks", sa.Column("embedding_config_id", sa.String(length=36), nullable=True))
    op.create_index("ix_notebooks_embedding_config_id", "notebooks", ["embedding_config_id"], unique=False)
    op.create_foreign_key(
        "fk_notebooks_embedding_config_id_embedding_configs",
        "notebooks",
        "embedding_configs",
        ["embedding_config_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_notebooks_embedding_config_id_embedding_configs", "notebooks", type_="foreignkey")
    op.drop_index("ix_notebooks_embedding_config_id", table_name="notebooks")
    op.drop_column("notebooks", "embedding_config_id")
