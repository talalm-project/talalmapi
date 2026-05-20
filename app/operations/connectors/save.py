from sqlalchemy import select

from app.models.connector import ALLOWED_CONNECTION_TYPES, Connector
from app.operations.validator import Validator


class Save(Validator):
    def __init__(
        self,
        session,
        user,
        code=None,
        name=None,
        connection_type=None,
        local_file_path=None,
        api_key=None,
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
        self.connection_type = connection_type
        self.local_file_path = local_file_path
        self.api_key = api_key
        self.data = data
        self.changed_fields = changed_fields or set()
        self.payload = {
            "code": [],
            "name": [],
            "connection_type": [],
            "api_key": [],
            "data": [],
        }

    def execute(self):
        self._validate()

        if self.valid():
            if self.connector is None:
                self.connector = Connector(
                    user_id=self.user.id,
                    code=self._normalized_code(),
                    name=self.name,
                    connection_type=self._connection_type(),
                    local_file_path=self.local_file_path,
                    api_key=self.api_key,
                    data=self.data,
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
        if self.connection_type and self.connection_type not in ALLOWED_CONNECTION_TYPES:
            self.payload["connection_type"].append("invalid")

        connection_type = self._connection_type()
        api_key = self._api_key()
        if connection_type == "openai" and _blank(api_key):
            self.payload["api_key"].append("required")

        code = self._normalized_code()
        if self._should_validate_code() and code and self._code_taken(code):
            self.payload["code"].append("already taken")

        self.count_errors()

    def _assign_updates(self):
        if "code" in self.changed_fields:
            self.connector.code = self._normalized_code()
        if "name" in self.changed_fields:
            self.connector.name = self.name
        if "connection_type" in self.changed_fields:
            self.connector.connection_type = self.connection_type
        if "local_file_path" in self.changed_fields:
            self.connector.local_file_path = self.local_file_path
        if "api_key" in self.changed_fields:
            self.connector.api_key = self.api_key
        if "data" in self.changed_fields and self.data is not None:
            self.connector.data = self.data

    def _connection_type(self):
        if self.connector is None:
            return self.connection_type or "local"

        return self.connection_type if "connection_type" in self.changed_fields else self.connector.connection_type

    def _api_key(self):
        if self.connector is None:
            return self.api_key

        return self.api_key if "api_key" in self.changed_fields else self.connector.api_key

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
