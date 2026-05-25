import re

from sqlalchemy import bindparam, select, text

from app.models.notebook_file import NotebookFile
from app.models.notebook_vector import NotebookVector
from app.operations.notebooks.generate_query_embedding import GenerateQueryEmbedding


DEFAULT_RETRIEVAL_K = 5
MAX_RETRIEVAL_K = 500
TARGET_FILE_NEIGHBOR_RADIUS = 1
RERANK_CANDIDATE_MULTIPLIER = 3


class RetrieveContext:
    def __init__(self, session, notebook, query, k=None, target_query=None):
        self.session = session
        self.notebook = notebook
        self.query = query
        self.target_query = target_query
        self.k = _normalized_k(k)
        self.query_embedding = None
        self.target_notebook_file_ids = []
        self.target_notebook_files = {}
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

        self.target_notebook_file_ids = self._target_notebook_file_ids()
        self.target_notebook_files = self._target_notebook_files_by_id(self.target_notebook_file_ids)
        self.chunks = self._nearest_chunks()
        if self.target_notebook_file_ids:
            self.chunks = self._with_neighbor_chunks(self.chunks)

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
        target_file_ids = self.target_notebook_file_ids
        if len(target_file_ids) > 1:
            return self._nearest_chunks_by_target_file(target_file_ids)

        file_filter = "AND notebook_file_id IN :target_notebook_file_ids" if target_file_ids else ""
        statement = text(
            f"""
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
                  {file_filter}
                ORDER BY distance ASC
                LIMIT :limit
                """
        )
        if target_file_ids:
            statement = statement.bindparams(bindparam("target_notebook_file_ids", expanding=True))

        params = {
            "query_embedding": _vector_literal(self.query_embedding),
            "notebook_id": self.notebook.id,
            "embedding_config_id": self.notebook.embedding_config_id,
            "limit": self._candidate_limit(self.k),
        }
        if target_file_ids:
            params["target_notebook_file_ids"] = target_file_ids

        rows = self.session.execute(statement, params).mappings()

        return self._reranked_chunks([_chunk_from_row(row) for row in rows], self.query)[: self.k]

    def _nearest_chunks_by_target_file(self, target_file_ids):
        per_file_limit = max(self.k // len(target_file_ids), 1)
        remainder = self.k % len(target_file_ids)
        chunks_by_file = []

        for index, target_file_id in enumerate(target_file_ids):
            limit = per_file_limit + (1 if index < remainder else 0)
            query = self._query_for_target_file(target_file_id)
            embedding = self._embedding_for_query(query) or self.query_embedding
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
                      AND notebook_file_id = :target_notebook_file_id
                    ORDER BY distance ASC
                    LIMIT :limit
                    """
                ),
                {
                    "query_embedding": _vector_literal(embedding),
                    "notebook_id": self.notebook.id,
                    "embedding_config_id": self.notebook.embedding_config_id,
                    "target_notebook_file_id": target_file_id,
                    "limit": self._candidate_limit(limit),
                },
            ).mappings()
            chunks = [_chunk_from_row(row) for row in rows]
            chunks_by_file.append(self._reranked_chunks(chunks, query)[:limit])

        return _interleaved_chunks(chunks_by_file)

    def _embedding_for_query(self, query):
        operation = GenerateQueryEmbedding(self.notebook.connector, query)
        operation.execute()
        if not operation.valid():
            return None

        return operation.embedding

    def _query_for_target_file(self, target_file_id):
        notebook_file = self.target_notebook_files.get(target_file_id)
        if notebook_file is None:
            return self.query

        return "\n\n".join([self.query, f"Focus on: {notebook_file.name} {notebook_file.filename}"])

    def _target_notebook_files_by_id(self, file_ids):
        if not file_ids:
            return {}

        rows = self.session.execute(select(NotebookFile).where(NotebookFile.id.in_(file_ids))).scalars()
        return {notebook_file.id: notebook_file for notebook_file in rows}

    def _candidate_limit(self, limit):
        return min(max(limit * RERANK_CANDIDATE_MULTIPLIER, limit), MAX_RETRIEVAL_K)

    def _reranked_chunks(self, chunks, query):
        terms = _query_terms(query)
        if not terms:
            return chunks

        return sorted(
            chunks,
            key=lambda chunk: (
                -_lexical_score(chunk.get("text"), terms),
                chunk.get("distance") if chunk.get("distance") is not None else 999999,
            ),
        )

    def _target_notebook_file_ids(self):
        target_text = self.target_query if isinstance(self.target_query, str) and self.target_query.strip() else self.query
        if not isinstance(target_text, str) or not target_text.strip():
            return []

        normalized_target = _normalized_text(target_text)
        rows = self.session.execute(
            select(NotebookFile.id, NotebookFile.name, NotebookFile.filename)
            .where(NotebookFile.notebook_id == self.notebook.id)
            .where(NotebookFile.status == "active")
        ).all()

        file_ids = []
        for notebook_file_id, name, filename in rows:
            aliases = _file_aliases(name, filename)
            if any(alias and _phrase_in_text(alias, normalized_target) for alias in aliases):
                file_ids.append(notebook_file_id)

        return file_ids

    def _with_neighbor_chunks(self, chunks):
        if not chunks:
            return chunks

        chunk_keys = {
            (chunk.get("notebook_file_id"), chunk.get("chunk_index"))
            for chunk in chunks
            if chunk.get("notebook_file_id") and isinstance(chunk.get("chunk_index"), int)
        }
        neighbor_keys = set()
        for notebook_file_id, chunk_index in chunk_keys:
            for offset in range(-TARGET_FILE_NEIGHBOR_RADIUS, TARGET_FILE_NEIGHBOR_RADIUS + 1):
                if offset == 0:
                    continue
                neighbor_index = chunk_index + offset
                if neighbor_index >= 0:
                    neighbor_keys.add((notebook_file_id, neighbor_index))

        neighbor_keys = neighbor_keys - chunk_keys
        if not neighbor_keys:
            return chunks

        file_ids = sorted({notebook_file_id for notebook_file_id, _chunk_index in neighbor_keys})
        chunk_indexes = sorted({chunk_index for _notebook_file_id, chunk_index in neighbor_keys})
        rows = self.session.execute(
            select(
                NotebookVector.id,
                NotebookVector.notebook_id,
                NotebookVector.embedding_config_id,
                NotebookVector.notebook_file_id,
                NotebookVector.chunk_index,
                NotebookVector.text,
                NotebookVector.metadata_,
            )
            .where(NotebookVector.notebook_id == self.notebook.id)
            .where(NotebookVector.embedding_config_id == self.notebook.embedding_config_id)
            .where(NotebookVector.notebook_file_id.in_(file_ids))
            .where(NotebookVector.chunk_index.in_(chunk_indexes))
        ).all()

        neighbors = [
            {
                "id": row.id,
                "notebook_id": row.notebook_id,
                "embedding_config_id": row.embedding_config_id,
                "notebook_file_id": row.notebook_file_id,
                "chunk_index": row.chunk_index,
                "text": row.text,
                "metadata": row.metadata_ or {},
                "distance": None,
            }
            for row in rows
            if (row.notebook_file_id, row.chunk_index) in neighbor_keys
        ]

        merged = []
        seen_ids = set()
        for chunk in chunks:
            for entry in _neighbor_group(chunk, neighbors):
                if entry["id"] not in seen_ids:
                    merged.append(entry)
                    seen_ids.add(entry["id"])

        return merged


def _normalized_k(value):
    if value is None:
        return DEFAULT_RETRIEVAL_K

    return min(max(int(value), 1), MAX_RETRIEVAL_K)


def _vector_literal(vector):
    return "[" + ",".join(str(float(entry)) for entry in vector) + "]"


def _chunk_from_row(row):
    return {
        "id": row["id"],
        "notebook_id": row["notebook_id"],
        "embedding_config_id": row["embedding_config_id"],
        "notebook_file_id": row["notebook_file_id"],
        "chunk_index": row["chunk_index"],
        "text": row["text"],
        "metadata": row["metadata"] or {},
        "distance": float(row["distance"]) if row["distance"] is not None else None,
    }


def _query_terms(query):
    terms = set(_normalized_text(query).split())
    return {term for term in terms if len(term) >= 3 and term not in _STOP_WORDS}


def _lexical_score(text_value, terms):
    text_terms = set(_normalized_text(text_value).split())
    if not text_terms:
        return 0

    exact_matches = len(terms & text_terms)
    phrase_bonus = sum(1 for term in terms if term in _normalized_text(text_value))
    return exact_matches * 3 + phrase_bonus


def _interleaved_chunks(chunks_by_file):
    chunks = []
    max_length = max((len(file_chunks) for file_chunks in chunks_by_file), default=0)
    for index in range(max_length):
        for file_chunks in chunks_by_file:
            if index < len(file_chunks):
                chunks.append(file_chunks[index])

    return chunks


def _neighbor_group(chunk, neighbors):
    notebook_file_id = chunk.get("notebook_file_id")
    chunk_index = chunk.get("chunk_index")
    if not notebook_file_id or not isinstance(chunk_index, int):
        return [chunk]

    group = [
        neighbor
        for neighbor in neighbors
        if neighbor.get("notebook_file_id") == notebook_file_id
        and isinstance(neighbor.get("chunk_index"), int)
        and abs(neighbor.get("chunk_index") - chunk_index) <= TARGET_FILE_NEIGHBOR_RADIUS
    ]
    group.append(chunk)
    return sorted(
        group,
        key=lambda entry: entry.get("chunk_index") if isinstance(entry.get("chunk_index"), int) else chunk_index,
    )


def _file_aliases(name, filename):
    aliases = {_normalized_text(name), _normalized_text(filename)}
    if isinstance(filename, str) and "." in filename:
        aliases.add(_normalized_text(filename.rsplit(".", 1)[0]))

    return {alias for alias in aliases if alias}


def _normalized_text(value):
    if not isinstance(value, str):
        return ""

    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _phrase_in_text(phrase, text_value):
    return f" {phrase} " in f" {text_value} "


_STOP_WORDS = {
    "about",
    "and",
    "are",
    "between",
    "can",
    "compare",
    "comparison",
    "for",
    "from",
    "how",
    "into",
    "tell",
    "the",
    "this",
    "what",
    "with",
    "you",
}
