"""create papers

Revision ID: 0019_create_papers
Revises: 0018_note_context_prompt
Create Date: 2026-06-24 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0019_create_papers"
down_revision = "0018_note_context_prompt"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "papers",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("papers")
