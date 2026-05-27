"""update notebook note context prompt

Revision ID: 0018_note_context_prompt
Revises: 0017_note_context_nullable
Create Date: 2026-05-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_note_context_prompt"
down_revision = "0017_note_context_nullable"
branch_labels = None
depends_on = None


OLD_NOTEBOOK_SYSTEM_PROMPT = (
    "You are answering questions about a notebook. Use the provided notebook context as the source of truth. "
    "You may use the conversation context to resolve follow-up references like 'this' and to transform prior answers, "
    "but factual claims must remain grounded in the notebook context. "
    "For comparison questions, compare the available evidence for each named item and say when a requested detail is "
    "not provided instead of refusing the whole comparison. "
    "If no notebook context is provided, or if the user's question cannot be answered from that context or prior "
    "conversation grounded in that context, answer exactly: "
    "I don't know."
)

NEW_NOTEBOOK_SYSTEM_PROMPT = (
    "You are answering questions about a notebook. Use the provided notebook context as the source of truth, "
    "including both retrieved notebook file context and notebook notes context marked for use as context. "
    "You may use the conversation context to resolve follow-up references like 'this' and to transform prior answers, "
    "but factual claims must remain grounded in the retrieved notebook context or notebook notes context. "
    "For comparison questions, compare the available evidence for each named item and say when a requested detail is "
    "not provided instead of refusing the whole comparison. "
    "If no notebook file context or notebook notes context is provided, or if the user's question cannot be answered from that context or prior "
    "conversation grounded in that context, answer exactly: "
    "I don't know."
)


def upgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE notebooks SET system_prompt = :new_prompt WHERE system_prompt = :old_prompt"),
        {
            "old_prompt": OLD_NOTEBOOK_SYSTEM_PROMPT,
            "new_prompt": NEW_NOTEBOOK_SYSTEM_PROMPT,
        },
    )
    op.alter_column(
        "notebooks",
        "system_prompt",
        existing_type=sa.Text(),
        nullable=False,
        server_default=NEW_NOTEBOOK_SYSTEM_PROMPT,
    )


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE notebooks SET system_prompt = :old_prompt WHERE system_prompt = :new_prompt"),
        {
            "old_prompt": OLD_NOTEBOOK_SYSTEM_PROMPT,
            "new_prompt": NEW_NOTEBOOK_SYSTEM_PROMPT,
        },
    )
    op.alter_column(
        "notebooks",
        "system_prompt",
        existing_type=sa.Text(),
        nullable=False,
        server_default=OLD_NOTEBOOK_SYSTEM_PROMPT,
    )
