from app.operations.notebooks.access import visible_notebook
from app.operations.notebooks.ensure_embedding_configs import EnsureEmbeddingConfigs


class Show:
    def __init__(self, session, user, notebook_id):
        self.session = session
        self.user = user
        self.notebook_id = notebook_id
        self.notebook = None

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user, admin_allowed=False)
        if self.notebook is None:
            return

        EnsureEmbeddingConfigs(self.session, [self.notebook]).execute()

    def found(self):
        return self.notebook is not None
