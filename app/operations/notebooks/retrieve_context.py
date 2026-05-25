from sqlalchemy import select, text

from app.models.notebook_vector import NotebookVector
from app.operations.notebooks.generate_query_embedding import GenerateQueryEmbedding


DEFAULT_RETRIEVAL_K = 5
MAX_RETRIEVAL_K = 500


class RetrieveContext:
    def __init__(self, session, notebook, query, k=None):
        self.session = session
        self.notebook = notebook
        self.query = query
        self.k = _normalized_k(k)
        self.query_embedding = None
        self.chunks = []
        self.errors = {}

    def execute(self):
        self.errors = self._validation_errors()
        self.query_embedding = None
        self.chunks = []
        if self.errors:
            return

        if not self._has_vectors():
            return

        operation = GenerateQueryEmbedding(self.notebook.connector, self.query)
        operation.execute()
        if not operation.valid():
            self.errors = operation.errors
            return

        self.query_embedding = operation.embedding
        if not self.query_embedding:
            self.errors = {"embedding": ["failed"]}
            return

        self.chunks = self._nearest_chunks()

    def valid(self):
        return not self.errors

    def _validation_errors(self):
        errors = {}
        if self.notebook is None:
            errors["notebook"] = ["required"]
            return errors

        if self.notebook.embedding_config_id is None:
            errors["embedding_config"] = ["required"]
        if not isinstance(self.query, str) or not self.query.strip():
            errors["query"] = ["required"]

        return errors

    def _has_vectors(self):
        vector_id = self.session.scalar(
            select(NotebookVector.id)
            .where(NotebookVector.notebook_id == self.notebook.id)
            .where(NotebookVector.embedding_config_id == self.notebook.embedding_config_id)
            .limit(1)
        )
        return vector_id is not None

    def _nearest_chunks(self):
        rows = self.session.execute(
            text(
                """
                SELECT
                    id,
                    notebook_id,
                    embedding_config_id,
                    notebook_file_id,
                    chunk_index,
                    text,
                    metadata,
                    embedding <=> CAST(:query_embedding AS vector) AS distance
                FROM notebook_vectors
                WHERE notebook_id = :notebook_id
                  AND embedding_config_id = :embedding_config_id
                ORDER BY distance ASC
                LIMIT :limit
                """
            ),
            {
                "query_embedding": _vector_literal(self.query_embedding),
                "notebook_id": self.notebook.id,
                "embedding_config_id": self.notebook.embedding_config_id,
                "limit": self.k,
            },
        ).mappings()

        return [
            {
                "id": row["id"],
                "notebook_id": row["notebook_id"],
                "embedding_config_id": row["embedding_config_id"],
                "notebook_file_id": row["notebook_file_id"],
                "chunk_index": row["chunk_index"],
                "text": row["text"],
                "metadata": row["metadata"] or {},
                "distance": float(row["distance"]) if row["distance"] is not None else None,
            }
            for row in rows
        ]


def _normalized_k(value):
    if value is None:
        return DEFAULT_RETRIEVAL_K

    return min(max(int(value), 1), MAX_RETRIEVAL_K)


def _vector_literal(vector):
    return "[" + ",".join(str(float(entry)) for entry in vector) + "]"
