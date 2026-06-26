from pydantic import BaseModel, Field


class PaperCreate(BaseModel):
    name: str | None = None


class PaperUpdate(BaseModel):
    name: str | None = None
    data: dict | None = None


class PaperRead(BaseModel):
    id: str
    user_id: str
    name: str
    data: dict


class PaperCollection(BaseModel):
    records: list[PaperRead] = Field(default_factory=list)


class PaperLatexSupportInference(BaseModel):
    user_prompt: str | None = None
    note_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
