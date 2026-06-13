from app.models.notebook_vector import NotebookVector
from app.operations.notebooks.embed_notebook_file import EmbedNotebookFile
from spec.factories import ConnectorFactory, NotebookFactory, NotebookFileFactory, NotebookVectorFactory


def test_embed_notebook_file_generates_vectors_and_marks_file_active(db_session, app, monkeypatch):
    connector = ConnectorFactory(
        connection_type="local",
        data={
            "metadata": {
                "provider": "local",
                "embeddings": {
                    "model": {
                        "name": "Local Embedding",
                        "local_file_path": "/tmp/embedding.gguf",
                        "embedding_size": 3,
                    },
                    "model_options": {"n_ctx": 2048},
                    "chunking": {"chunk_size": 10, "chunk_overlap": 2},
                    "limits": {"max_input_tokens": 512},
                },
            }
        },
    )
    notebook = NotebookFactory(connector=connector)
    notebook_file = NotebookFileFactory(
        notebook=notebook,
        filename="notes.txt",
        object_key="notebooks/notes-key",
        status="pending",
    )
    stale_vector = NotebookVectorFactory(
        notebook=notebook,
        notebook_file=notebook_file,
        embedding_config=notebook.embedding_config,
    )
    captured = {}

    def fake_download(settings, key, destination_path):
        captured["download"] = {
            "bucket": settings.STORAGE_S3_BUCKET,
            "key": key,
            "destination_path": destination_path,
        }
        destination_path.write_text("hello notebook", encoding="utf-8")

    class FakeGenerateLocalEmbeddings:
        def __init__(self, **kwargs):
            captured["generator"] = kwargs
            self.embeddings = [
                {"text": "hello", "embedding": [0.1, 0.2, 0.3], "metadata": {"page": 1}},
                {"text": "notebook", "embedding": [0.4, 0.5, 0.6], "metadata": {"page": 2}},
            ]
            self.errors = {}

        def execute(self):
            captured["executed"] = True

        def invalid(self):
            return False

    monkeypatch.setattr("app.operations.notebooks.embed_notebook_file.download_file_to_path", fake_download)
    monkeypatch.setattr(
        "app.operations.notebooks.embed_notebook_file.GenerateLocalEmbeddings",
        lambda **kwargs: FakeGenerateLocalEmbeddings(**kwargs),
    )

    operation = EmbedNotebookFile(db_session, app.state.settings, notebook_file)
    operation.execute()

    assert operation.valid()
    assert captured["download"]["bucket"] == "talalm-test"
    assert captured["download"]["key"] == "notebooks/notes-key"
    assert captured["generator"]["local_embedding_model"] == connector
    assert captured["generator"]["chunk_size"] == 10
    assert captured["generator"]["chunk_overlap"] == 2
    assert captured["generator"]["model_options"] == {"n_ctx": 2048}
    assert captured["generator"]["max_input_tokens"] == 512
    assert captured["generator"]["source_name"] == "notes.txt"
    assert captured["executed"] is True

    db_session.expire_all()
    assert db_session.get(type(notebook_file), notebook_file.id).status == "active"
    assert db_session.get(NotebookVector, stale_vector.id) is None

    vectors = db_session.query(NotebookVector).filter_by(notebook_file_id=notebook_file.id).order_by(NotebookVector.chunk_index).all()
    assert len(vectors) == 2
    assert vectors[0].notebook_id == notebook.id
    assert vectors[0].embedding_config_id == notebook.embedding_config_id
    assert vectors[0].text == "hello"
    assert vectors[0].embedding == [0.1, 0.2, 0.3]
    assert vectors[0].metadata_ == {"page": 1}
    assert vectors[1].chunk_index == 1


def test_embed_notebook_file_marks_file_failed_when_generator_errors(db_session, app, monkeypatch):
    notebook_file = NotebookFileFactory(filename="notes.txt", object_key="broken-key", status="pending")

    monkeypatch.setattr(
        "app.operations.notebooks.embed_notebook_file.download_file_to_path",
        lambda settings, key, destination_path: destination_path.write_text("hello", encoding="utf-8"),
    )

    class FakeGenerateLocalEmbeddings:
        errors = {"input_file": ["no text found"]}
        embeddings = []

        def __init__(self, **kwargs):
            pass

        def execute(self):
            pass

        def invalid(self):
            return True

    monkeypatch.setattr(
        "app.operations.notebooks.embed_notebook_file.GenerateLocalEmbeddings",
        lambda **kwargs: FakeGenerateLocalEmbeddings(**kwargs),
    )

    operation = EmbedNotebookFile(db_session, app.state.settings, notebook_file)
    operation.execute()

    assert operation.invalid()
    db_session.expire_all()
    failed_file = db_session.get(type(notebook_file), notebook_file.id)
    assert failed_file.status == "failed"
    assert failed_file.error_message == "Unable to embed notebook file."
    assert db_session.query(NotebookVector).filter_by(notebook_file_id=notebook_file.id).count() == 0


def test_embed_notebook_file_sanitizes_vector_text_before_insert(db_session, app, monkeypatch):
    notebook_file = NotebookFileFactory(filename="notes.txt", object_key="nul-key", status="pending")

    monkeypatch.setattr(
        "app.operations.notebooks.embed_notebook_file.download_file_to_path",
        lambda settings, key, destination_path: destination_path.write_text("hello", encoding="utf-8"),
    )

    class FakeGenerateLocalEmbeddings:
        errors = {}
        embeddings = [
            {"text": "hello\x00 notebook", "embedding": [0.1, 0.2, 0.3], "metadata": {}},
        ]

        def __init__(self, **kwargs):
            pass

        def execute(self):
            pass

        def invalid(self):
            return False

    monkeypatch.setattr(
        "app.operations.notebooks.embed_notebook_file.GenerateLocalEmbeddings",
        lambda **kwargs: FakeGenerateLocalEmbeddings(**kwargs),
    )

    operation = EmbedNotebookFile(db_session, app.state.settings, notebook_file)
    operation.execute()

    assert operation.valid()
    db_session.expire_all()
    vector = db_session.query(NotebookVector).filter_by(notebook_file_id=notebook_file.id).one()
    assert vector.text == "hello notebook"


def test_embed_notebook_file_rolls_back_before_marking_failed(db_session, app, monkeypatch):
    notebook_file = NotebookFileFactory(filename="notes.txt", object_key="flush-error-key", status="pending")
    rollback_calls = []
    original_rollback = db_session.rollback

    monkeypatch.setattr(
        "app.operations.notebooks.embed_notebook_file.download_file_to_path",
        lambda settings, key, destination_path: destination_path.write_text("hello", encoding="utf-8"),
    )

    class FakeGenerateLocalEmbeddings:
        errors = {}
        embeddings = [
            {"text": "hello", "embedding": [0.1, 0.2, 0.3], "metadata": {}},
        ]

        def __init__(self, **kwargs):
            pass

        def execute(self):
            pass

        def invalid(self):
            return False

    def fake_rollback():
        rollback_calls.append(True)
        original_rollback()

    monkeypatch.setattr(
        "app.operations.notebooks.embed_notebook_file.GenerateLocalEmbeddings",
        lambda **kwargs: FakeGenerateLocalEmbeddings(**kwargs),
    )
    monkeypatch.setattr(db_session, "rollback", fake_rollback)
    monkeypatch.setattr(
        EmbedNotebookFile,
        "_replace_vectors",
        lambda self, embeddings: (_ for _ in ()).throw(RuntimeError("flush failed")),
    )

    operation = EmbedNotebookFile(db_session, app.state.settings, notebook_file)
    operation.execute()

    assert operation.invalid()
    assert rollback_calls == [True]
    db_session.expire_all()
    failed_file = db_session.get(type(notebook_file), notebook_file.id)
    assert failed_file.status == "failed"
    assert failed_file.error_message == "flush failed"
