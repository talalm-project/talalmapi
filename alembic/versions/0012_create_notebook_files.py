"""create notebook files

Revision ID: 0012_notebook_files
Revises: 0011_active_notebook_default
Create Date: 2026-05-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0012_notebook_files"
down_revision = "0011_active_notebook_default"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notebook_files",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("notebook_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("checksum", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["notebook_id"], ["notebooks.id"]),
        sa.UniqueConstraint("object_key", name="uq_notebook_files_object_key"),
    )
    op.create_index("ix_notebook_files_notebook_id", "notebook_files", ["notebook_id"], unique=False)
    op.create_index("ix_notebook_files_status", "notebook_files", ["status"], unique=False)
    op.create_foreign_key(
        "fk_notebook_vectors_notebook_file_id_notebook_files",
        "notebook_vectors",
        "notebook_files",
        ["notebook_file_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_notebook_vectors_notebook_file_id_notebook_files", "notebook_vectors", type_="foreignkey")
    op.drop_index("ix_notebook_files_status", table_name="notebook_files")
    op.drop_index("ix_notebook_files_notebook_id", table_name="notebook_files")
    op.drop_table("notebook_files")
