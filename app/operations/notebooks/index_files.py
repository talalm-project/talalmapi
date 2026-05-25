from sqlalchemy import select

from app.models.notebook_file import NotebookFile
from app.operations.notebooks.access import visible_notebook


class IndexFiles:
    def __init__(self, session, user, notebook_id):
        self.session = session
        self.user = user
        self.notebook_id = notebook_id
        self.notebook = None
        self.notebook_files = []

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user)
        if self.notebook is None:
            return

        self.notebook_files = (
            self.session.execute(
                select(NotebookFile)
                .where(NotebookFile.notebook_id == self.notebook.id)
                .order_by(NotebookFile.created_at.desc())
            )
            .scalars()
            .all()
        )

    def found(self):
        return self.notebook is not None

    def to_dict(self):
        return {"records": [notebook_file.to_dict() for notebook_file in self.notebook_files]}
