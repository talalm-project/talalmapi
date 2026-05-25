from sqlalchemy import delete as sql_delete

from app.models.notebook_file import NotebookFile
from app.models.notebook_vector import NotebookVector
from app.operations.notebooks.access import visible_notebook
from app.operations.validator import Validator
from app.storage import delete_file


DELETABLE_NOTEBOOK_FILE_STATUSES = {"pending", "active"}


class DestroyFile(Validator):
    def __init__(self, session, user, settings, notebook_id, notebook_file_id):
        super().__init__()
        self.session = session
        self.user = user
        self.settings = settings
        self.notebook_id = notebook_id
        self.notebook_file_id = notebook_file_id
        self.notebook = None
        self.notebook_file = None
        self.notebook_found = False
        self.notebook_file_found = False
        self.payload = {
            "status": [],
        }

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user)
        self.notebook_found = self.notebook is not None
        if self.notebook is None:
            return

        self.notebook_file = self.session.get(NotebookFile, self.notebook_file_id)
        self.notebook_file_found = self.notebook_file is not None and self.notebook_file.notebook_id == self.notebook.id
        if not self.notebook_file_found:
            return

        if self.notebook_file.status not in DELETABLE_NOTEBOOK_FILE_STATUSES:
            self.payload["status"].append("cannot delete")
            self.count_errors()
            return

        delete_file(self.settings, self.notebook_file.object_key)
        self.session.execute(sql_delete(NotebookVector).where(NotebookVector.notebook_file_id == self.notebook_file.id))
        self.session.delete(self.notebook_file)
        self.session.commit()

    def found(self):
        return self.notebook_found and self.notebook_file_found
