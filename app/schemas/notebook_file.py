from pydantic import BaseModel


class NotebookFileOut(BaseModel):
    id: str
    notebook_id: str
    name: str
    filename: str
    content_type: str | None = None
    byte_size: int | None = None
    object_key: str
    checksum: str | None = None
    status: str
    error_message: str | None = None
    data: dict


class NotebookFileCollection(BaseModel):
    records: list[NotebookFileOut]
