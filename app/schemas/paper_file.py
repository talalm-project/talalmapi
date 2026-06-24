from pydantic import BaseModel, Field


class PaperFileRead(BaseModel):
    id: str
    paper_id: str
    path: str
    filename: str
    content_type: str | None = None
    size: int | None = None
    storage_key: str
    created_at: str | None = None
    updated_at: str | None = None


class PaperFileCollection(BaseModel):
    records: list[PaperFileRead] = Field(default_factory=list)


class PaperFileContentRead(BaseModel):
    file: PaperFileRead
    editable: bool
    content: str | None = None
    message: str | None = None


class PaperFileContentUpdate(BaseModel):
    content: str | None = None
    last_known_updated_at: str | None = None
