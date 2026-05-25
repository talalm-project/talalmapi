from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.user import utcnow


class EmbeddingConfig(Base):
    __tablename__ = "embedding_configs"
    __table_args__ = (
        CheckConstraint("dimensions > 0", name="ck_embedding_configs_dimensions_positive"),
        UniqueConstraint("config_hash", name="uq_embedding_configs_config_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    connector_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("connectors.id"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_metric: Mapped[str] = mapped_column(String(50), nullable=False, default="cosine")
    options: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    connector = relationship("Connector", back_populates="embedding_configs")
    notebooks = relationship("Notebook", back_populates="embedding_config")
    notebook_vectors = relationship("NotebookVector", back_populates="embedding_config")

    def to_dict(self):
        return {
            "id": self.id,
            "connector_id": self.connector_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "model_path": self.model_path,
            "dimensions": self.dimensions,
            "distance_metric": self.distance_metric,
            "options": self.options,
            "config_hash": self.config_hash,
        }
