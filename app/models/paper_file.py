from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.user import utcnow


class PaperFile(Base):
    __tablename__ = "paper_files"
    __table_args__ = (
        UniqueConstraint("paper_id", "path", name="uq_paper_files_paper_id_path"),
        UniqueConstraint("storage_key", name="uq_paper_files_storage_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    paper_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("papers.id"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(1200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    paper = relationship("Paper", back_populates="files")

    def to_dict(self):
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "path": self.path,
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "storage_key": self.storage_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
