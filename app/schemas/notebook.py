from pydantic import BaseModel


class NotebookOut(BaseModel):
    id: str
    title: str
    data: dict
    user_id: str
    connector_id: str
    status: str


class NotebookCollection(BaseModel):
    records: list[NotebookOut]
    total_pages: int
    current_page: int
    next_page: int | None
    prev_page: int | None
