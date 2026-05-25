from spec.factories import EmbeddingConfigFactory, NotebookFactory, NotebookVectorFactory


def test_embedding_config_factory_creates_connector_config(db_session):
    embedding_config = EmbeddingConfigFactory(dimensions=1536)

    assert embedding_config.id is not None
    assert embedding_config.connector_id == embedding_config.connector.id
    assert embedding_config.provider == embedding_config.connector.connection_type
    assert embedding_config.dimensions == 1536
    assert embedding_config.distance_metric == "cosine"
    assert embedding_config.to_dict()["config_hash"] == embedding_config.config_hash


def test_notebook_vector_factory_creates_vector_for_matching_notebook_and_config(db_session):
    notebook = NotebookFactory()
    embedding_config = EmbeddingConfigFactory(connector=notebook.connector)

    notebook_vector = NotebookVectorFactory(
        notebook=notebook,
        embedding_config=embedding_config,
        chunk_index=2,
        embedding=[0.1, 0.2, 0.3],
        metadata_={"page": 1},
    )

    assert notebook_vector.id is not None
    assert notebook_vector.notebook_id == notebook.id
    assert notebook_vector.embedding_config_id == embedding_config.id
    assert notebook_vector.embedding == [0.1, 0.2, 0.3]
    assert notebook_vector.to_dict()["metadata"] == {"page": 1}
