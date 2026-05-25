"""create embedding configs and notebook vectors

Revision ID: 0009_embedding_vectors
Revises: 0008_create_notebooks
Create Date: 2026-05-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import UserDefinedType


revision = "0009_embedding_vectors"
down_revision = "0008_create_notebooks"
branch_labels = None
depends_on = None


class Vector(UserDefinedType):
    def get_col_spec(self, **_kw):
        return "vector"


def upgrade():
    op.create_table(
        "embedding_configs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("connector_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_path", sa.String(length=1024), nullable=True),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("distance_metric", sa.String(length=50), nullable=False, server_default="cosine"),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("dimensions > 0", name="ck_embedding_configs_dimensions_positive"),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"]),
        sa.UniqueConstraint("config_hash", name="uq_embedding_configs_config_hash"),
    )
    op.create_index("ix_embedding_configs_connector_id", "embedding_configs", ["connector_id"], unique=False)

    op.create_table(
        "notebook_vectors",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("notebook_id", sa.String(length=36), nullable=False),
        sa.Column("embedding_config_id", sa.String(length=36), nullable=False),
        sa.Column("notebook_file_id", sa.String(length=36), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["embedding_config_id"], ["embedding_configs.id"]),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"]),
        sa.UniqueConstraint("notebook_id", "notebook_file_id", "chunk_index", name="uq_notebook_vectors_file_chunk"),
    )
    op.create_index("ix_notebook_vectors_embedding_config_id", "notebook_vectors", ["embedding_config_id"], unique=False)
    op.create_index("ix_notebook_vectors_notebook_file_id", "notebook_vectors", ["notebook_file_id"], unique=False)
    op.create_index("ix_notebook_vectors_notebook_id", "notebook_vectors", ["notebook_id"], unique=False)
    op.create_index(
        "ix_notebook_vectors_notebook_id_embedding_config_id",
        "notebook_vectors",
        ["notebook_id", "embedding_config_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_notebook_vectors_notebook_id_embedding_config_id", table_name="notebook_vectors")
    op.drop_index("ix_notebook_vectors_notebook_id", table_name="notebook_vectors")
    op.drop_index("ix_notebook_vectors_notebook_file_id", table_name="notebook_vectors")
    op.drop_index("ix_notebook_vectors_embedding_config_id", table_name="notebook_vectors")
    op.drop_table("notebook_vectors")
    op.drop_index("ix_embedding_configs_connector_id", table_name="embedding_configs")
    op.drop_table("embedding_configs")
