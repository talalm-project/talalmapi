from pydantic import BaseModel, Field


class ConnectorCreate(BaseModel):
    name: str | None = None
    connection_type: str | None = None
    local_file_path: str | None = None
    api_key: str | None = None
    data: dict = Field(default_factory=dict)


class ConnectorUpdate(BaseModel):
    name: str | None = None
    connection_type: str | None = None
    local_file_path: str | None = None
    api_key: str | None = None
    data: dict | None = None


class ConnectorOut(BaseModel):
    id: str
    user_id: str
    name: str
    connection_type: str
    local_file_path: str | None = None
    data: dict


class ConnectorCollection(BaseModel):
    records: list[ConnectorOut]
