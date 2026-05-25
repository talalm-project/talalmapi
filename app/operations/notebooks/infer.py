from app.models.notebook import DEFAULT_NOTEBOOK_SYSTEM_PROMPT
from app.operations.connectors.infer import Infer as ConnectorInfer
from app.operations.notebooks.access import visible_notebook


class Infer:
    def __init__(self, session, user, notebook_id, payload):
        self.session = session
        self.user = user
        self.notebook_id = notebook_id
        self.payload = payload
        self.notebook = None
        self.response = None
        self.errors = {}

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user)
        if self.notebook is None:
            return

        system_prompt = self.notebook.system_prompt or DEFAULT_NOTEBOOK_SYSTEM_PROMPT
        operation = ConnectorInfer(self.notebook.connector, self.payload, system_prompt=system_prompt)
        operation.execute()
        if not operation.valid():
            self.errors = operation.errors
            return

        self.response = operation.response

    def found(self):
        return self.notebook is not None

    def valid(self):
        return not self.errors
