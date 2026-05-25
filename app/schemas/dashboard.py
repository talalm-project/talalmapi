from pydantic import BaseModel

from app.schemas.connector import ConnectorOut
from app.schemas.notebook import NotebookListOut
from app.schemas.notebook_file import NotebookFileOut


class DashboardSummary(BaseModel):
    notebooks_count: int
    active_notebooks_count: int
    connectors_count: int
    local_connectors_count: int
    openai_connectors_count: int
    active_files_count: int
    queued_files_count: int
    failed_files_count: int
    notebooks_without_files_count: int
    total_file_bytes: int
    needs_attention_count: int


class DashboardFileSummary(BaseModel):
    active: int
    queued: int
    failed: int
    total: int


class DashboardNotebookRow(BaseModel):
    notebook: NotebookListOut
    connector: ConnectorOut | None = None
    health: str
    file_summary: DashboardFileSummary


class DashboardConnectorRow(BaseModel):
    connector: ConnectorOut
    notebooks_count: int


class DashboardAttentionFile(NotebookFileOut):
    notebook: NotebookListOut | None = None


class DashboardOut(BaseModel):
    summary: DashboardSummary
    notebooks: list[DashboardNotebookRow]
    connectors: list[DashboardConnectorRow]
    attention_files: list[DashboardAttentionFile]
