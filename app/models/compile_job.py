from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.user import utcnow


ALLOWED_COMPILE_JOB_STATUSES = {"pending", "running", "success", "failed"}
ALLOWED_LATEX_COMPILERS = {"pdflatex", "xelatex", "lualatex"}


class CompileJob(Base):
    __tablename__ = "compile_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    paper_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("papers.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    compiler: Mapped[str] = mapped_column(String(50), nullable=False, default="pdflatex")
    builder: Mapped[str] = mapped_column(String(50), nullable=False, default="latexmk")
    main_file: Mapped[str] = mapped_column(String(1024), nullable=False, default="main.tex")
    output_pdf_key: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    log_key: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    paper = relationship("Paper", back_populates="compile_jobs")

    def to_dict(self):
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "status": self.status,
            "compiler": self.compiler,
            "builder": self.builder,
            "main_file": self.main_file,
            "output_pdf_key": self.output_pdf_key,
            "log_key": self.log_key,
            "logs": self.logs,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
