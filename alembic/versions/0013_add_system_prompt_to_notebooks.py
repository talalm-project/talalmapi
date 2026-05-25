"""add system prompt to notebooks

Revision ID: 0013_notebook_system_prompt
Revises: 0012_notebook_files
Create Date: 2026-05-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_notebook_system_prompt"
down_revision = "0012_notebook_files"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notebooks", sa.Column("system_prompt", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("notebooks", "system_prompt")
