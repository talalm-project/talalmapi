from app.operations.notebooks.retrieve_context import DEFAULT_RETRIEVAL_K, MAX_RETRIEVAL_K, RetrieveContext
from spec.factories import EmbeddingConfigFactory, NotebookFactory, NotebookFileFactory, NotebookVectorFactory


def test_retrieve_context_filters_by_notebook_embedding_config_and_k(db_session, monkeypatch):
    notebook = NotebookFactory()
    other_config = EmbeddingConfigFactory(connector=notebook.connector)
    other_notebook = NotebookFactory()
    best = NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        chunk_index=1,
        text="Best matching context",
        embedding=[1.0, 0.0, 0.0],
    )
    second = NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        chunk_index=2,
        text="Second matching context",
        embedding=[0.8, 0.2, 0.0],
    )
    NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        chunk_index=3,
        text="Third matching context",
        embedding=[0.0, 1.0, 0.0],
    )
    NotebookVectorFactory(
        notebook=notebook,
        embedding_config=other_config,
        chunk_index=4,
        text="Wrong embedding config",
        embedding=[1.0, 0.0, 0.0],
    )
    NotebookVectorFactory(
        notebook=other_notebook,
        embedding_config=other_notebook.embedding_config,
        chunk_index=5,
        text="Wrong notebook",
        embedding=[1.0, 0.0, 0.0],
    )

    class FakeLlama:
        def __init__(self, **_kwargs):
            pass

        def create_embedding(self, _input):
            return {"data": [{"embedding": [1.0, 0.0, 0.0]}]}

    monkeypatch.setattr("app.operations.notebooks.generate_query_embedding._llama_class", lambda: FakeLlama)

    operation = RetrieveContext(db_session, notebook, "What is relevant?", k=2)
    operation.execute()

    assert operation.valid()
    assert [chunk["id"] for chunk in operation.chunks] == [best.id, second.id]
    assert all(chunk["notebook_id"] == notebook.id for chunk in operation.chunks)
    assert all(chunk["embedding_config_id"] == notebook.embedding_config_id for chunk in operation.chunks)


def test_retrieve_context_filters_to_named_notebook_file(db_session, monkeypatch):
    notebook = NotebookFactory()
    convnext_file = NotebookFileFactory(notebook=notebook, name="ConvNext", filename="2301.00808v1.pdf", status="active")
    mobilenet_file = NotebookFileFactory(notebook=notebook, name="MobileNetV4", filename="2404.10518v2.pdf", status="active")
    intro = NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        notebook_file=convnext_file,
        chunk_index=0,
        text="ConvNeXt paper introduction",
        embedding=[0.0, 1.0, 0.0],
    )
    convnext = NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        notebook_file=convnext_file,
        chunk_index=1,
        text="ConvNeXt related literature",
        embedding=[0.8, 0.2, 0.0],
    )
    NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        notebook_file=mobilenet_file,
        chunk_index=2,
        text="MobileNetV4 related literature",
        embedding=[1.0, 0.0, 0.0],
    )

    class FakeLlama:
        def __init__(self, **_kwargs):
            pass

        def create_embedding(self, _input):
            return {"data": [{"embedding": [1.0, 0.0, 0.0]}]}

    monkeypatch.setattr("app.operations.notebooks.generate_query_embedding._llama_class", lambda: FakeLlama)

    operation = RetrieveContext(
        db_session,
        notebook,
        "Current question: What about related literature for ConvNeXt?\n\nRecent conversation: MobileNetV4 details",
        k=1,
        target_query="What about related literature for ConvNeXt?",
    )
    operation.execute()

    assert operation.valid()
    assert operation.target_notebook_file_ids == [convnext_file.id]
    assert [chunk["id"] for chunk in operation.chunks] == [intro.id, convnext.id]


def test_retrieve_context_balances_multiple_named_notebook_files(db_session, monkeypatch):
    notebook = NotebookFactory()
    convnext_file = NotebookFileFactory(notebook=notebook, name="ConvNext", filename="2301.00808v1.pdf", status="active")
    efficientnet_file = NotebookFileFactory(notebook=notebook, name="EfficientNet", filename="1905.11946v5.pdf", status="active")
    mobilenet_file = NotebookFileFactory(notebook=notebook, name="MobileNetV4", filename="2404.10518v2.pdf", status="active")
    convnext_best = NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        notebook_file=convnext_file,
        chunk_index=1,
        text="ConvNeXt architecture",
        embedding=[0.9, 0.1, 0.0],
    )
    efficientnet_best = NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        notebook_file=efficientnet_file,
        chunk_index=1,
        text="EfficientNet architecture",
        embedding=[0.8, 0.2, 0.0],
    )
    NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        notebook_file=mobilenet_file,
        chunk_index=1,
        text="MobileNetV4 architecture",
        embedding=[1.0, 0.0, 0.0],
    )

    class FakeLlama:
        def __init__(self, **_kwargs):
            pass

        def create_embedding(self, _input):
            return {"data": [{"embedding": [1.0, 0.0, 0.0]}]}

    monkeypatch.setattr("app.operations.notebooks.generate_query_embedding._llama_class", lambda: FakeLlama)

    operation = RetrieveContext(
        db_session,
        notebook,
        "Current question: Compare ConvNext and EfficientNet",
        k=2,
        target_query="Compare ConvNext and EfficientNet",
    )
    operation.execute()

    assert operation.valid()
    assert operation.target_notebook_file_ids == [convnext_file.id, efficientnet_file.id]
    assert {chunk["id"] for chunk in operation.chunks} == {convnext_best.id, efficientnet_best.id}


def test_retrieve_context_defaults_and_caps_k():
    assert RetrieveContext(None, None, "", k=None).k == DEFAULT_RETRIEVAL_K
    assert RetrieveContext(None, None, "", k=0).k == 1
    assert RetrieveContext(None, None, "", k=MAX_RETRIEVAL_K + 5).k == MAX_RETRIEVAL_K


def test_retrieve_context_skips_embedding_when_notebook_has_no_vectors(db_session, monkeypatch):
    notebook = NotebookFactory()
    called = False

    class FakeLlama:
        def __init__(self, **_kwargs):
            nonlocal called
            called = True

    monkeypatch.setattr("app.operations.notebooks.generate_query_embedding._llama_class", lambda: FakeLlama)

    operation = RetrieveContext(db_session, notebook, "No files yet", k=3)
    operation.execute()

    assert operation.valid()
    assert operation.chunks == []
    assert called is False
