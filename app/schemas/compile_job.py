from pydantic import BaseModel, Field


class CompileJobRead(BaseModel):
    id: str
    paper_id: str
    status: str
    compiler: str
    builder: str
    main_file: str
    output_pdf_key: str | None = None
    log_key: str | None = None
    logs: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CompileJobCollection(BaseModel):
    records: list[CompileJobRead] = Field(default_factory=list)
