from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.user import utcnow
from app.models.vector import Vector


class NotebookVector(Base):
    __tablename__ = "notebook_vectors"
    __table_args__ = (
        UniqueConstraint("notebook_id", "notebook_file_id", "chunk_index", name="uq_notebook_vectors_file_chunk"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    notebook_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("notebooks.id"),
        nullable=False,
        index=True,
    )
    embedding_config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("embedding_configs.id"),
        nullable=False,
        index=True,
    )
    notebook_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    notebook = relationship("Notebook", back_populates="vectors")
    embedding_config = relationship("EmbeddingConfig", back_populates="notebook_vectors")

    def to_dict(self):
        return {
            "id": self.id,
            "notebook_id": self.notebook_id,
            "embedding_config_id": self.embedding_config_id,
            "notebook_file_id": self.notebook_file_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "embedding": self.embedding,
            "metadata": self.metadata_,
        }
