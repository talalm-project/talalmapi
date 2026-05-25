from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import delete as sql_delete

from app.models.notebook_vector import NotebookVector
from app.operations.connectors.metadata import embedding_chunk_options, embedding_max_input_tokens, embedding_model_options
from app.operations.embeddings import GenerateLocalEmbeddings, GenerateOpenAIEmbeddings
from app.operations.embeddings.generate_local_embeddings import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.operations.validator import Validator
from app.storage import download_file_to_path


class EmbedNotebookFile(Validator):
    def __init__(self, session, settings, notebook_file):
        super().__init__()
        self.session = session
        self.settings = settings
        self.notebook_file = notebook_file
        self.notebook = None
        self.embedding_config = None
        self.vectors = []
        self.payload = {
            "notebook_file": [],
            "notebook": [],
            "embedding_config": [],
            "connection_type": [],
            "embedding": [],
        }

    def execute(self):
        self._validate()
        if self.invalid():
            return

        self.notebook_file.status = "processing"
        self.notebook_file.error_message = None
        self.session.commit()
        self.session.refresh(self.notebook_file)

        try:
            with TemporaryDirectory() as temp_dir:
                input_path = Path(temp_dir) / self.notebook_file.filename
                download_file_to_path(self.settings, self.notebook_file.object_key, input_path)
                generator = self._embedding_generator(input_path)
                generator.execute()
                if generator.invalid():
                    self.payload["embedding"].append(generator.errors)
                    self.count_errors()
                    self._mark_failed()
                    return

                self._replace_vectors(generator.embeddings)

            self.notebook_file.status = "active"
            self.notebook_file.error_message = None
            self.session.commit()
            self.session.refresh(self.notebook_file)
        except Exception as error:
            self.payload["embedding"].append(str(error))
            self.count_errors()
            self._mark_failed(str(error))

    def _validate(self):
        if self.notebook_file is None:
            self.payload["notebook_file"].append("required")
            self.count_errors()
            return

        self.notebook = self.notebook_file.notebook
        if self.notebook is None:
            self.payload["notebook"].append("required")
        else:
            self.embedding_config = self.notebook.embedding_config
            if self.embedding_config is None:
                self.payload["embedding_config"].append("required")

        self.count_errors()

    def _embedding_generator(self, input_path):
        connector = self.notebook.connector
        chunk_size, chunk_overlap = embedding_chunk_options(connector, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP)

        if connector.connection_type == "local":
            return GenerateLocalEmbeddings(
                local_embedding_model=connector,
                input_file=input_path,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                model_options=embedding_model_options(connector),
                max_input_tokens=embedding_max_input_tokens(connector),
                source_name=self.notebook_file.filename,
            )

        if connector.connection_type == "openai":
            return GenerateOpenAIEmbeddings(
                connector=connector,
                input_file=input_path,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                source_name=self.notebook_file.filename,
            )

        self.payload["connection_type"].append("unsupported")
        self.count_errors()
        return _InvalidEmbeddingGenerator(self.payload)

    def _replace_vectors(self, embeddings):
        self.session.execute(
            sql_delete(NotebookVector).where(NotebookVector.notebook_file_id == self.notebook_file.id)
        )
        self.vectors = []
        for index, embedding_record in enumerate(embeddings):
            vector = NotebookVector(
                notebook_id=self.notebook.id,
                notebook_file_id=self.notebook_file.id,
                embedding_config_id=self.embedding_config.id,
                chunk_index=index,
                text=embedding_record["text"],
                embedding=embedding_record["embedding"],
                metadata_=embedding_record.get("metadata", {}),
            )
            self.session.add(vector)
            self.vectors.append(vector)

        self.session.flush()

    def _mark_failed(self, message=None):
        self.notebook_file.status = "failed"
        self.notebook_file.error_message = message or "Unable to embed notebook file."
        self.session.commit()
        self.session.refresh(self.notebook_file)


class _InvalidEmbeddingGenerator:
    def __init__(self, errors):
        self.errors = errors

    def execute(self):
        return None

    def invalid(self):
        return True
