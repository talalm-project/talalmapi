from sqlalchemy import delete as sql_delete, select

from app.models.notebook_file import NotebookFile
from app.models.notebook_vector import NotebookVector
from app.operations.notebooks.access import visible_notebook


class Reindex:
    def __init__(self, session, user, notebook_id):
        self.session = session
        self.user = user
        self.notebook_id = notebook_id
        self.notebook = None
        self.files = []
        self.deleted_vector_count = 0

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user)
        if self.notebook is None:
            return

        self.files = list(
            self.session.scalars(
                select(NotebookFile).where(NotebookFile.notebook_id == self.notebook.id).order_by(NotebookFile.created_at)
            )
        )
        file_ids = [notebook_file.id for notebook_file in self.files]
        if file_ids:
            result = self.session.execute(sql_delete(NotebookVector).where(NotebookVector.notebook_file_id.in_(file_ids)))
            self.deleted_vector_count = result.rowcount or 0

        for notebook_file in self.files:
            notebook_file.status = "pending"
            notebook_file.error_message = None

        self.session.commit()

    def found(self):
        return self.notebook is not None

    def to_dict(self):
        return {
            "message": "ok",
            "files": len(self.files),
            "deleted_vectors": self.deleted_vector_count,
        }
