from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.user import utcnow


ALLOWED_NOTEBOOK_STATUSES = {"pending", "processing", "active", "failed"}
DEFAULT_NOTEBOOK_SYSTEM_PROMPT = (
    "You are answering questions about a notebook. Use only the provided context pulled from the notebook files. "
    "If no context is provided, or if the user's question cannot be answered from that context, answer exactly: "
    "I don't know."
)


class Notebook(Base):
    __tablename__ = "notebooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default=DEFAULT_NOTEBOOK_SYSTEM_PROMPT)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    connector_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("connectors.id"),
        nullable=False,
        index=True,
    )
    embedding_config_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("embedding_configs.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    user = relationship("User", back_populates="notebooks")
    connector = relationship("Connector", back_populates="notebooks")
    embedding_config = relationship("EmbeddingConfig", back_populates="notebooks")
    files = relationship("NotebookFile", back_populates="notebook")
    vectors = relationship("NotebookVector", back_populates="notebook")

    def to_dict(self, include_connector=False):
        payload = {
            "id": self.id,
            "title": self.title,
            "system_prompt": self.system_prompt,
            "data": self.data,
            "user_id": self.user_id,
            "connector_id": self.connector_id,
            "embedding_config_id": self.embedding_config_id,
            "status": self.status,
        }

        if include_connector:
            payload["connector"] = self.connector.to_dict() if self.connector is not None else None

        return payload
