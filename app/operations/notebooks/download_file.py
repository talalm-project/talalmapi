from app.models.notebook_file import NotebookFile
from app.operations.notebooks.access import visible_notebook
from app.storage import get_file


class DownloadFile:
    def __init__(self, session, user, settings, notebook_id, notebook_file_id):
        self.session = session
        self.user = user
        self.settings = settings
        self.notebook_id = notebook_id
        self.notebook_file_id = notebook_file_id
        self.notebook = None
        self.notebook_file = None
        self.file_response = None
        self.notebook_found = False
        self.notebook_file_found = False

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user)
        self.notebook_found = self.notebook is not None
        if self.notebook is None:
            return

        self.notebook_file = self.session.get(NotebookFile, self.notebook_file_id)
        self.notebook_file_found = self.notebook_file is not None and self.notebook_file.notebook_id == self.notebook.id
        if not self.notebook_file_found:
            return

        self.file_response = get_file(self.settings, self.notebook_file.object_key)

    def found(self):
        return self.notebook_found and self.notebook_file_found
