from app.models.notebook_note import NotebookNote
from app.operations.notebooks.access import visible_notebook
from app.operations.validator import Validator


class CreateNote(Validator):
    def __init__(self, session, user, notebook_id, name=None, data=None):
        super().__init__()
        self.session = session
        self.user = user
        self.notebook_id = notebook_id
        self.name = name
        self.data = data
        self.notebook = None
        self.notebook_note = None
        self.payload = {
            "name": [],
            "data": [],
        }

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user, admin_allowed=False)
        if self.notebook is None:
            return

        self._validate()
        if self.invalid():
            return

        self.notebook_note = NotebookNote(
            notebook_id=self.notebook.id,
            name=self.name.strip(),
            data=self.data,
        )
        self.session.add(self.notebook_note)
        self.session.commit()
        self.session.refresh(self.notebook_note)

    def found(self):
        return self.notebook is not None

    def _validate(self):
        if self.name is None or not self.name.strip():
            self.payload["name"].append("required")
        if self.data is None:
            self.payload["data"].append("required")

        self.count_errors()
