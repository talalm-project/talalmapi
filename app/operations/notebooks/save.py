from copy import deepcopy

from app.models.connector import Connector
from app.models.notebook import DEFAULT_NOTEBOOK_SYSTEM_PROMPT, Notebook
from app.operations.embedding_configs import Resolve as ResolveEmbeddingConfig
from app.operations.validator import Validator


class Save(Validator):
    def __init__(
        self,
        session,
        user,
        title=None,
        system_prompt=None,
        connector_id=None,
        notebook=None,
    ):
        super().__init__()
        self.session = session
        self.user = user
        self.title = title
        self.system_prompt = system_prompt
        self.connector_id = connector_id
        self.connector = None
        self.notebook = notebook
        self.payload = {
            "title": [],
            "connector_id": [],
            "embedding_config": [],
        }

    def execute(self):
        self._validate()

        if self.invalid():
            return

        if self.notebook is not None:
            self.notebook.title = self.title.strip()
            self.session.commit()
            self.session.refresh(self.notebook)
        else:
            embedding_config = self._resolve_embedding_config()
            if self.invalid():
                return

            self.notebook = Notebook(
                title=self.title.strip(),
                system_prompt=self._normalized_system_prompt(),
                user_id=self.user.id,
                connector_id=self.connector.id,
                embedding_config_id=embedding_config.id,
                data={"connector": deepcopy(self.connector.data or {})},
                status="active",
            )
            self.session.add(self.notebook)
            self.session.commit()
            self.session.refresh(self.notebook)

    def _validate(self):
        if self.title is None or not self.title.strip():
            self.payload["title"].append("required")

        if self.notebook is not None:
            self.count_errors()
            return

        if self.connector_id is None or not str(self.connector_id).strip():
            self.payload["connector_id"].append("required")
        else:
            self.connector = self.session.get(Connector, self.connector_id)
            if self.connector is None or self.connector.user_id != self.user.id:
                self.payload["connector_id"].append("not found")

        self.count_errors()

    def _resolve_embedding_config(self):
        operation = ResolveEmbeddingConfig(session=self.session, connector=self.connector)
        operation.execute()
        if operation.invalid():
            self.payload["embedding_config"].append(operation.payload)
            self.count_errors()
            return None

        return operation.embedding_config

    def _normalized_system_prompt(self):
        if self.system_prompt is None:
            return DEFAULT_NOTEBOOK_SYSTEM_PROMPT

        normalized_prompt = self.system_prompt.strip()
        return normalized_prompt or DEFAULT_NOTEBOOK_SYSTEM_PROMPT
