"""create compile jobs

Revision ID: 0022_compile_jobs
Revises: 0021_paper_files
Create Date: 2026-06-24 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_compile_jobs"
down_revision = "0021_paper_files"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "compile_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("compiler", sa.String(length=50), nullable=False, server_default="pdflatex"),
        sa.Column("builder", sa.String(length=50), nullable=False, server_default="latexmk"),
        sa.Column("main_file", sa.String(length=1024), nullable=False, server_default="main.tex"),
        sa.Column("output_pdf_key", sa.String(length=1200), nullable=True),
        sa.Column("log_key", sa.String(length=1200), nullable=True),
        sa.Column("logs", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]),
    )
    op.create_index("ix_compile_jobs_paper_id", "compile_jobs", ["paper_id"], unique=False)
    op.create_index("ix_compile_jobs_status", "compile_jobs", ["status"], unique=False)


def downgrade():
    op.drop_index("ix_compile_jobs_status", table_name="compile_jobs")
    op.drop_index("ix_compile_jobs_paper_id", table_name="compile_jobs")
    op.drop_table("compile_jobs")
