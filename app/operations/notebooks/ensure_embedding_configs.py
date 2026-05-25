from app.operations.embedding_configs import Resolve as ResolveEmbeddingConfig


class EnsureEmbeddingConfigs:
    def __init__(self, session, notebooks):
        self.session = session
        self.notebooks = notebooks

    def execute(self):
        changed = False
        for notebook in self.notebooks:
            if notebook.embedding_config_id is not None:
                continue

            operation = ResolveEmbeddingConfig(session=self.session, connector=notebook.connector)
            operation.execute()
            if operation.invalid():
                continue

            notebook.embedding_config_id = operation.embedding_config.id
            changed = True

        if changed:
            self.session.commit()
            for notebook in self.notebooks:
                self.session.refresh(notebook)
