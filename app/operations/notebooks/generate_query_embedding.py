from app.operations.connectors.metadata import embedding_max_input_tokens, embedding_model_options
from app.operations.embeddings.generate_local_embeddings import _embedding_from_response, _llama_class


class GenerateQueryEmbedding:
    def __init__(self, connector, query):
        self.connector = connector
        self.query = query
        self.embedding = None
        self.errors = {}

    def execute(self):
        self.errors = self._validation_errors()
        self.embedding = None
        if self.errors:
            return

        self.embedding = self._local_embedding()

    def valid(self):
        return not self.errors

    def _validation_errors(self):
        errors = {}
        if not isinstance(self.query, str) or not self.query.strip():
            errors["query"] = ["required"]

        model_path = self._local_model_path()
        if not model_path:
            errors["embedding_local_file_path"] = ["required"]
        elif not model_path.lower().endswith(".gguf"):
            errors["embedding_local_file_path"] = ["must be a .gguf model"]

        return errors

    def _local_embedding(self):
        llm = _llama_class()(model_path=self._local_model_path(), embedding=True, **embedding_model_options(self.connector))
        max_input_tokens = embedding_max_input_tokens(self.connector)
        query = self.query.strip()
        if max_input_tokens is not None:
            query = query[:max_input_tokens]
        return _embedding_from_response(llm.create_embedding(query))

    def _local_model_path(self):
        from app.operations.connectors.metadata import embedding_local_file_path

        return embedding_local_file_path(self.connector)
