from typing import Any

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
    user_prompt: Any = None
    connector_id: Any = None
    note_ids: Any = Field(default_factory=list)
    document_ids: Any = Field(default_factory=list)
    notebook_id: Any = None
    notebook_note_ids: Any = Field(default_factory=list)
    notebook_file_ids: Any = Field(default_factory=list)
