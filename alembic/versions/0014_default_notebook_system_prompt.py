"""default notebook system prompt

Revision ID: 0014_default_nb_prompt
Revises: 0013_notebook_system_prompt
Create Date: 2026-05-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_default_nb_prompt"
down_revision = "0013_notebook_system_prompt"
branch_labels = None
depends_on = None


DEFAULT_NOTEBOOK_SYSTEM_PROMPT = (
    "You are answering questions about a notebook. Use only the provided context pulled from the notebook files. "
    "If no context is provided, or if the user's question cannot be answered from that context, answer exactly: "
    "I don't know."
)


def upgrade():
    escaped_prompt = DEFAULT_NOTEBOOK_SYSTEM_PROMPT.replace("'", "''")
    op.execute(
        f"UPDATE notebooks SET system_prompt = '{escaped_prompt}' "
        "WHERE system_prompt IS NULL OR btrim(system_prompt) = ''"
    )
    op.alter_column(
        "notebooks",
        "system_prompt",
        existing_type=sa.Text(),
        nullable=False,
        server_default=DEFAULT_NOTEBOOK_SYSTEM_PROMPT,
    )


def downgrade():
    op.alter_column(
        "notebooks",
        "system_prompt",
        existing_type=sa.Text(),
        nullable=True,
        server_default=None,
    )
