from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select

from app.models.embedding_config import EmbeddingConfig
from app.models.notebook import Notebook
from app.models.notebook_file import NotebookFile
from app.models.notebook_note import NotebookNote
from app.models.notebook_vector import NotebookVector
from app.operations.notebooks.access import visible_notebook


class Destroy:
    def __init__(self, session, user, notebook_id):
        self.session = session
        self.user = user
        self.notebook_id = notebook_id
        self.notebook = None

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user)
        if self.notebook is None:
            return

        embedding_config_id = self.notebook.embedding_config_id
        self.session.execute(sql_delete(NotebookVector).where(NotebookVector.notebook_id == self.notebook.id))
        self.session.execute(sql_delete(NotebookFile).where(NotebookFile.notebook_id == self.notebook.id))
        self.session.execute(sql_delete(NotebookNote).where(NotebookNote.notebook_id == self.notebook.id))
        self.session.delete(self.notebook)
        self.session.flush()

        if embedding_config_id is not None and _embedding_config_unused(self.session, embedding_config_id):
            embedding_config = self.session.get(EmbeddingConfig, embedding_config_id)
            if embedding_config is not None:
                self.session.delete(embedding_config)

        self.session.commit()

    def found(self):
        return self.notebook is not None


def _embedding_config_unused(session, embedding_config_id):
    notebook_count = (
        session.scalar(select(func.count()).select_from(Notebook).where(Notebook.embedding_config_id == embedding_config_id))
        or 0
    )
    if notebook_count > 0:
        return False

    vector_count = (
        session.scalar(
            select(func.count()).select_from(NotebookVector).where(NotebookVector.embedding_config_id == embedding_config_id)
        )
        or 0
    )
    return vector_count == 0
