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
