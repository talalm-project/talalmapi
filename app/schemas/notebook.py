from pydantic import BaseModel, Field

from app.schemas.connector import ConnectorInfer


class NotebookCreate(BaseModel):
    title: str | None = None
    system_prompt: str | None = None
    connector_id: str | None = None


class NotebookUpdate(BaseModel):
    title: str | None = None


class NotebookInfer(ConnectorInfer):
    manual_retrieval: bool = False
    document_ids: list[str] = Field(default_factory=list)


class NotebookConnectorOut(BaseModel):
    id: str
    user_id: str
    code: str
    name: str
    local_file_path: str | None = None
    embedding_local_file_path: str | None = None
    embedding_name: str | None = None
    data: dict


class NotebookListOut(BaseModel):
    id: str
    title: str
    system_prompt: str | None = None
    data: dict
    user_id: str
    connector_id: str
    embedding_config_id: str | None = None
    status: str
    files_count: int = 0


class NotebookOut(NotebookListOut):
    connector: NotebookConnectorOut | None = None


class NotebookCollection(BaseModel):
    records: list[NotebookListOut]
    total_pages: int
    current_page: int
    next_page: int | None
    prev_page: int | None
