from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.user import utcnow


ALLOWED_CONNECTION_TYPES = {"local", "openai"}


class Connector(Base):
    __tablename__ = "connectors"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_connectors_user_id_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connection_type: Mapped[str] = mapped_column(String(50), nullable=False)
    local_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    embedding_local_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    embedding_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    user = relationship("User", back_populates="connectors")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "code": self.code,
            "name": self.name,
            "connection_type": self.connection_type,
            "local_file_path": self.local_file_path,
            "embedding_local_file_path": self.embedding_local_file_path,
            "embedding_name": self.embedding_name,
            "data": self.data,
        }
