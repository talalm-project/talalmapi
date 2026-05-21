from pathlib import Path

from app.operations.connectors.metadata import embedding_model_name, embedding_size
from app.operations.embeddings.generate_local_embeddings import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    MissingParserDependency,
    SUPPORTED_INPUT_EXTENSIONS,
    _chunk_text,
    _clean_text,
    _extract_docx,
    _extract_pdf,
    _extract_pptx,
    _extract_txt,
    _extract_xlsx,
    _get_value,
)


class GenerateOpenAIEmbeddings:
    def __init__(
        self,
        connector,
        input_file,
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
        source_name=None,
    ):
        self.connector = connector
        self.input_file = input_file
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.source_name = source_name
        self.errors = {}
        self.chunks = []
        self.embeddings = []

    def execute(self):
        self.errors = self._validation_errors()
        self.chunks = []
        self.embeddings = []
        if self.errors:
            return

        try:
            blocks = self._extract_text_blocks()
        except MissingParserDependency as error:
            self.errors = {"input_file": [f"missing parser dependency: {error.package_name}"]}
            return

        self.chunks = self._chunk_blocks(blocks)
        if not self.chunks:
            self.errors = {"input_file": ["no text found"]}
            return

        client = _openai_client_class()(api_key=self.connector.api_key)
        create_options = {
            "model": self._model_name(),
            "input": [chunk["text"] for chunk in self.chunks],
        }
        dimensions = self._dimensions()
        if dimensions is not None:
            create_options["dimensions"] = dimensions

        response = client.embeddings.create(**create_options)
        data = _get_value(response, "data") or []
        self.embeddings = [
            {
                "text": chunk["text"],
                "embedding": _get_value(data[index], "embedding") if index < len(data) else None,
                "metadata": self._metadata_for_chunk(chunk, index),
            }
            for index, chunk in enumerate(self.chunks)
        ]

    def valid(self):
        return not self.errors

    def invalid(self):
        return bool(self.errors)

    def _validation_errors(self):
        errors = {}
        input_path = self._input_path()

        if not self.connector.api_key:
            errors["api_key"] = ["required"]
        if not self._model_name():
            errors["embedding_name"] = ["required"]

        if input_path is None:
            errors["input_file"] = ["required"]
        elif not input_path.exists():
            errors["input_file"] = ["not found"]
        elif not input_path.is_file():
            errors["input_file"] = ["invalid"]
        elif input_path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
            errors["input_file"] = ["unsupported file type"]

        if not isinstance(self.chunk_size, int) or self.chunk_size <= 0:
            errors["chunk_size"] = ["must be greater than 0"]
        if not isinstance(self.chunk_overlap, int) or self.chunk_overlap < 0:
            errors["chunk_overlap"] = ["must be greater than or equal to 0"]
        if (
            isinstance(self.chunk_size, int)
            and isinstance(self.chunk_overlap, int)
            and self.chunk_size > 0
            and self.chunk_overlap >= self.chunk_size
        ):
            errors["chunk_overlap"] = ["must be less than chunk_size"]

        return errors

    def _extract_text_blocks(self):
        input_path = self._input_path()
        extension = input_path.suffix.lower()

        if extension == ".txt":
            return _extract_txt(input_path)
        if extension == ".docx":
            return _extract_docx(input_path)
        if extension == ".pptx":
            return _extract_pptx(input_path)
        if extension == ".xlsx":
            return _extract_xlsx(input_path)
        if extension == ".pdf":
            return _extract_pdf(input_path)

        return []

    def _chunk_blocks(self, blocks):
        chunks = []
        for block in blocks:
            text = _clean_text(block.get("text"))
            if not text:
                continue

            chunks.extend(
                {
                    "text": chunk_text,
                    "metadata": block.get("metadata", {}),
                }
                for chunk_text in _chunk_text(text, self.chunk_size, self.chunk_overlap)
            )

        return chunks

    def _metadata_for_chunk(self, chunk, index):
        input_path = self._input_path()
        metadata = {
            "source": str(input_path),
            "source_name": self.source_name or input_path.name,
            "extension": input_path.suffix.lower(),
            "chunk_index": index,
            "model": self._model_name(),
            "embedding_size": self._dimensions(),
        }
        metadata.update(chunk.get("metadata", {}))
        return metadata

    def _input_path(self):
        if self.input_file is None:
            return None

        try:
            return Path(self.input_file)
        except TypeError:
            return None

    def _model_name(self):
        return embedding_model_name(self.connector)

    def _dimensions(self):
        model_name = self._model_name() or ""
        if not model_name.startswith("text-embedding-3-"):
            return None

        return embedding_size(self.connector)


def _openai_client_class():
    from openai import OpenAI

    return OpenAI
