"""create paper files

Revision ID: 0021_paper_files
Revises: 0020_papers_user
Create Date: 2026-06-24 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_paper_files"
down_revision = "0020_papers_user"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "paper_files",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("storage_key", sa.String(length=1200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]),
        sa.UniqueConstraint("paper_id", "path", name="uq_paper_files_paper_id_path"),
        sa.UniqueConstraint("storage_key", name="uq_paper_files_storage_key"),
    )
    op.create_index("ix_paper_files_paper_id", "paper_files", ["paper_id"], unique=False)


def downgrade():
    op.drop_index("ix_paper_files_paper_id", table_name="paper_files")
    op.drop_table("paper_files")
