from app.operations.connectors.metadata import embedding_max_input_tokens, embedding_model_name, embedding_model_options, embedding_size
from app.operations.embeddings.generate_local_embeddings import _embedding_from_response, _llama_class
from app.operations.embeddings.generate_openai_embeddings import _openai_client_class


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

        if self.connector.connection_type == "local":
            self.embedding = self._local_embedding()
            return

        if self.connector.connection_type == "openai":
            self.embedding = self._openai_embedding()
            return

        self.errors = {"connection_type": ["unsupported"]}

    def valid(self):
        return not self.errors

    def _validation_errors(self):
        errors = {}
        if not isinstance(self.query, str) or not self.query.strip():
            errors["query"] = ["required"]

        if self.connector.connection_type == "local":
            model_path = self._local_model_path()
            if not model_path:
                errors["embedding_local_file_path"] = ["required"]
            elif not model_path.lower().endswith(".gguf"):
                errors["embedding_local_file_path"] = ["must be a .gguf model"]

        if self.connector.connection_type == "openai":
            if not self.connector.api_key:
                errors["api_key"] = ["required"]
            if not embedding_model_name(self.connector):
                errors["embedding_name"] = ["required"]

        return errors

    def _local_embedding(self):
        llm = _llama_class()(model_path=self._local_model_path(), embedding=True, **embedding_model_options(self.connector))
        max_input_tokens = embedding_max_input_tokens(self.connector)
        query = self.query.strip()
        if max_input_tokens is not None:
            query = query[:max_input_tokens]
        return _embedding_from_response(llm.create_embedding(query))

    def _openai_embedding(self):
        client = _openai_client_class()(api_key=self.connector.api_key)
        create_options = {
            "model": embedding_model_name(self.connector),
            "input": self.query.strip(),
        }
        dimensions = self._openai_dimensions()
        if dimensions is not None:
            create_options["dimensions"] = dimensions

        response = client.embeddings.create(**create_options)
        data = _get_value(response, "data") or []
        if not data:
            return None

        return _get_value(data[0], "embedding")

    def _openai_dimensions(self):
        model_name = embedding_model_name(self.connector) or ""
        if not model_name.startswith("text-embedding-3-"):
            return None

        return embedding_size(self.connector)

    def _local_model_path(self):
        from app.operations.connectors.metadata import embedding_local_file_path

        return embedding_local_file_path(self.connector)


def _get_value(source, key):
    if isinstance(source, dict):
        return source.get(key)

    return getattr(source, key, None)
