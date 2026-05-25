from typing import Any

from pydantic import BaseModel, Field


class ConnectorCreate(BaseModel):
    code: str | None = None
    name: str | None = None
    connection_type: str | None = None
    local_file_path: str | None = None
    embedding_local_file_path: str | None = None
    embedding_name: str | None = None
    api_key: str | None = None
    data: dict = Field(default_factory=dict)


class ConnectorUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    connection_type: str | None = None
    local_file_path: str | None = None
    embedding_local_file_path: str | None = None
    embedding_name: str | None = None
    api_key: str | None = None
    data: dict | None = None


class ConnectorOut(BaseModel):
    id: str
    user_id: str
    code: str
    name: str
    connection_type: str
    local_file_path: str | None = None
    embedding_local_file_path: str | None = None
    embedding_name: str | None = None
    data: dict


class ConnectorCollection(BaseModel):
    records: list[ConnectorOut]


class ConnectorInfer(BaseModel):
    prompt: str | None = None
    input: Any = None
    model: str | None = None
    options: dict = Field(default_factory=dict)
    k: int | None = Field(default=None, ge=1, le=500)
