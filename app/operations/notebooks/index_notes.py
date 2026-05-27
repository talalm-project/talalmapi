from sqlalchemy import select

from app.models.notebook_note import NotebookNote
from app.operations.notebooks.access import visible_notebook


class IndexNotes:
    def __init__(self, session, user, notebook_id):
        self.session = session
        self.user = user
        self.notebook_id = notebook_id
        self.notebook = None
        self.notebook_notes = []

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user)
        if self.notebook is None:
            return

        self.notebook_notes = (
            self.session.execute(
                select(NotebookNote)
                .where(NotebookNote.notebook_id == self.notebook.id)
                .order_by(NotebookNote.created_at.desc())
            )
            .scalars()
            .all()
        )

    def found(self):
        return self.notebook is not None

    def to_dict(self):
        return {"records": [notebook_note.to_dict() for notebook_note in self.notebook_notes]}
