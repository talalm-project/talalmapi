from copy import deepcopy

from app.models.connector import Connector
from app.models.notebook import Notebook
from app.operations.validator import Validator


class Save(Validator):
    def __init__(
        self,
        session,
        user,
        title=None,
        connector_id=None,
    ):
        super().__init__()
        self.session = session
        self.user = user
        self.title = title
        self.connector_id = connector_id
        self.connector = None
        self.notebook = None
        self.payload = {
            "title": [],
            "connector_id": [],
        }

    def execute(self):
        self._validate()

        if self.valid():
            self.notebook = Notebook(
                title=self.title.strip(),
                user_id=self.user.id,
                connector_id=self.connector.id,
                data=deepcopy(self.connector.data or {}),
                status="pending",
            )
            self.session.add(self.notebook)
            self.session.commit()
            self.session.refresh(self.notebook)

    def _validate(self):
        if self.title is None or not self.title.strip():
            self.payload["title"].append("required")

        if self.connector_id is None or not str(self.connector_id).strip():
            self.payload["connector_id"].append("required")
        else:
            self.connector = self.session.get(Connector, self.connector_id)
            if self.connector is None or self.connector.user_id != self.user.id:
                self.payload["connector_id"].append("not found")

        self.count_errors()
