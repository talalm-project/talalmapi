from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import select

from app.models.notebook_file import NotebookFile
from app.operations.embeddings.generate_local_embeddings import (
    MissingParserDependency,
    SUPPORTED_INPUT_EXTENSIONS,
    _clean_text,
)
from app.operations.embeddings.generate_local_embeddings import extract_text_blocks
from app.storage import download_file_to_path


class ManualRetrieveContext:
    def __init__(self, session, settings, notebook, document_ids=None):
        self.session = session
        self.settings = settings
        self.notebook = notebook
        self.document_ids = document_ids or []
        self.notebook_files = []
        self.chunks = []
        self.errors = {}

    def execute(self):
        self.errors = self._validation_errors()
        self.chunks = []
        if self.errors:
            return

        self.notebook_files = self._notebook_files()
        if len(self.notebook_files) != len(set(self.document_ids)):
            self.errors = {"document_ids": ["invalid"]}
            return

        try:
            self.chunks = self._document_chunks()
        except MissingParserDependency as error:
            self.errors = {"document_ids": [f"missing parser dependency: {error.package_name}"]}
        except Exception as error:
            self.errors = {"document_ids": [str(error)]}

    def valid(self):
        return not self.errors

    def _validation_errors(self):
        errors = {}
        if self.notebook is None:
            errors["notebook"] = ["required"]
        if not isinstance(self.document_ids, list) or not self.document_ids:
            errors["document_ids"] = ["required"]
        elif any(not isinstance(document_id, str) or not document_id.strip() for document_id in self.document_ids):
            errors["document_ids"] = ["invalid"]

        return errors

    def _notebook_files(self):
        rows = (
            self.session.execute(
                select(NotebookFile)
                .where(NotebookFile.notebook_id == self.notebook.id)
                .where(NotebookFile.id.in_(self.document_ids))
            )
            .scalars()
            .all()
        )
        files_by_id = {notebook_file.id: notebook_file for notebook_file in rows}
        return [files_by_id[document_id] for document_id in self.document_ids if document_id in files_by_id]

    def _document_chunks(self):
        chunks = []
        with TemporaryDirectory() as temp_dir:
            for notebook_file in self.notebook_files:
                input_path = Path(temp_dir) / notebook_file.filename
                if input_path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
                    self.errors = {"document_ids": [f"unsupported file type: {notebook_file.filename}"]}
                    return []

                download_file_to_path(self.settings, notebook_file.object_key, input_path)
                extracted_text = "\n\n".join(
                    _clean_text(block.get("text")) for block in extract_text_blocks(input_path)
                )
                text = _clean_text(extracted_text)
                if not text:
                    continue

                chunks.append(
                    {
                        "id": notebook_file.id,
                        "notebook_id": self.notebook.id,
                        "embedding_config_id": self.notebook.embedding_config_id,
                        "notebook_file_id": notebook_file.id,
                        "chunk_index": 0,
                        "text": text,
                        "metadata": {"manual_retrieval": True, "source_name": notebook_file.filename},
                        "distance": None,
                    }
                )

        if not chunks:
            self.errors = {"document_ids": ["no text found"]}

        return chunks
