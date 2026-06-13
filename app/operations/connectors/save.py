from sqlalchemy import select

from app.models.connector import Connector
from app.operations.connectors.metadata import build_connector_data
from app.operations.validator import Validator


class Save(Validator):
    def __init__(
        self,
        session,
        user,
        code=None,
        name=None,
        local_file_path=None,
        embedding_local_file_path=None,
        embedding_name=None,
        data=None,
        changed_fields=None,
        connector=None,
    ):
        super().__init__()
        self.session = session
        self.user = user
        self.connector = connector
        self.code = code
        self.name = name
        self.local_file_path = local_file_path
        self.embedding_local_file_path = embedding_local_file_path
        self.embedding_name = embedding_name
        self.data = data
        self.changed_fields = changed_fields or set()
        self.payload = {
            "code": [],
            "name": [],
            "data": [],
        }

    def execute(self):
        self._validate()

        if self.valid():
            if self.connector is None:
                connector_attrs = {
                    "code": self._normalized_code(),
                    "name": self.name,
                    "local_file_path": self.local_file_path,
                    "embedding_local_file_path": self.embedding_local_file_path,
                    "embedding_name": self.embedding_name,
                }
                self.connector = Connector(
                    user_id=self.user.id,
                    code=self._normalized_code(),
                    name=self.name,
                    connection_type="local",
                    local_file_path=self.local_file_path,
                    embedding_local_file_path=self.embedding_local_file_path,
                    embedding_name=self.embedding_name,
                    data=build_connector_data(connector_attrs, self.data),
                )
                self.session.add(self.connector)
            else:
                self._assign_updates()

            self.session.commit()
            self.session.refresh(self.connector)

    def _validate(self):
        if self.connector is None:
            if self.code is None:
                self.payload["code"].append("required")
            if self.name is None:
                self.payload["name"].append("required")

        if self.code is not None and not self.code.strip():
            self.payload["code"].append("required")
        if self.name is not None and not self.name.strip():
            self.payload["name"].append("required")
        if self.data is not None and not isinstance(self.data, dict):
            self.payload["data"].append("invalid")

        code = self._normalized_code()
        if self._should_validate_code() and code and self._code_taken(code):
            self.payload["code"].append("already taken")

        self.count_errors()

    def _assign_updates(self):
        if "code" in self.changed_fields:
            self.connector.code = self._normalized_code()
        if "name" in self.changed_fields:
            self.connector.name = self.name
        if "local_file_path" in self.changed_fields:
            self.connector.local_file_path = self.local_file_path
        if "embedding_local_file_path" in self.changed_fields:
            self.connector.embedding_local_file_path = self.embedding_local_file_path
        if "embedding_name" in self.changed_fields:
            self.connector.embedding_name = self.embedding_name
        data = self.connector.data or {}
        if "data" in self.changed_fields and self.data is not None:
            data = self.data
        self.connector.data = build_connector_data(self.connector, data)

    def _normalized_code(self):
        if self.code is not None:
            return self.code.strip()

        if self.connector is not None:
            return self.connector.code

        return None

    def _should_validate_code(self):
        return self.connector is None or "code" in self.changed_fields

    def _code_taken(self, code):
        stmt = select(Connector).where(Connector.user_id == self.user.id).where(Connector.code == code)
        if self.connector is not None:
            stmt = stmt.where(Connector.id != self.connector.id)

        return self.session.scalar(stmt) is not None


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())
