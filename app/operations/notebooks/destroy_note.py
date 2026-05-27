from app.models.notebook_note import NotebookNote
from app.operations.notebooks.access import visible_notebook


class DestroyNote:
    def __init__(self, session, user, notebook_id, notebook_note_id):
        self.session = session
        self.user = user
        self.notebook_id = notebook_id
        self.notebook_note_id = notebook_note_id
        self.notebook = None
        self.notebook_note = None
        self.notebook_found = False
        self.notebook_note_found = False

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user)
        self.notebook_found = self.notebook is not None
        if self.notebook is None:
            return

        self.notebook_note = self.session.get(NotebookNote, self.notebook_note_id)
        self.notebook_note_found = self.notebook_note is not None and self.notebook_note.notebook_id == self.notebook.id
        if not self.notebook_note_found:
            return

        self.session.delete(self.notebook_note)
        self.session.commit()

    def found(self):
        return self.notebook_found and self.notebook_note_found
