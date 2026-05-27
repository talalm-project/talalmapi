from pydantic import BaseModel


class NotebookNoteCreate(BaseModel):
    name: str
    data: dict


class NotebookNoteOut(BaseModel):
    id: str
    notebook_id: str
    name: str
    data: dict
    is_context: bool | None


class NotebookNoteCollection(BaseModel):
    records: list[NotebookNoteOut]
