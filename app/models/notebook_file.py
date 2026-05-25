import secrets
from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.user import utcnow


ALLOWED_NOTEBOOK_FILE_STATUSES = {"pending", "uploading", "uploaded", "processing", "active", "failed"}


def generate_object_key():
    return secrets.token_urlsafe(24)


class NotebookFile(Base):
    __tablename__ = "notebook_files"
    __table_args__ = (UniqueConstraint("object_key", name="uq_notebook_files_object_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    notebook_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("notebooks.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False, default=generate_object_key)
    checksum: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    notebook = relationship("Notebook", back_populates="files")
    vectors = relationship("NotebookVector", back_populates="notebook_file")

    def to_dict(self):
        return {
            "id": self.id,
            "notebook_id": self.notebook_id,
            "name": self.name,
            "filename": self.filename,
            "content_type": self.content_type,
            "byte_size": self.byte_size,
            "object_key": self.object_key,
            "checksum": self.checksum,
            "status": self.status,
            "error_message": self.error_message,
            "data": self.data,
        }
