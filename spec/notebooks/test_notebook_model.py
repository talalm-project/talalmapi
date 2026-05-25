from app.models.notebook import ALLOWED_NOTEBOOK_STATUSES, DEFAULT_NOTEBOOK_SYSTEM_PROMPT, Notebook
from spec.factories import ConnectorFactory, EmbeddingConfigFactory, NotebookFactory


def test_notebook_factory_creates_notebook(db_session):
    connector = ConnectorFactory(data={"llm": {"model": "llama"}})
    notebook = NotebookFactory(connector=connector, data=connector.data)

    assert notebook.id is not None
    assert notebook.title.startswith("Notebook ")
    assert notebook.data == {"llm": {"model": "llama"}}
    assert notebook.user_id == connector.user_id
    assert notebook.user == connector.user
    assert notebook.connector_id == connector.id
    assert notebook.connector == connector
    assert notebook.embedding_config_id == notebook.embedding_config.id
    assert notebook.system_prompt == DEFAULT_NOTEBOOK_SYSTEM_PROMPT
    assert notebook.status == "active"
    assert notebook.created_at is not None
    assert notebook.updated_at is not None


def test_notebook_defaults(db_session):
    connector = ConnectorFactory()
    embedding_config = EmbeddingConfigFactory(connector=connector)
    notebook = Notebook(
        title="Defaulted Notebook",
        user=connector.user,
        connector=connector,
        embedding_config=embedding_config,
    )

    db_session.add(notebook)
    db_session.commit()

    assert notebook.data == {}
    assert notebook.system_prompt == DEFAULT_NOTEBOOK_SYSTEM_PROMPT
    assert notebook.status == "active"


def test_notebook_to_dict_returns_public_fields(db_session):
    notebook = NotebookFactory(
        title="Research Notes",
        system_prompt="Answer using notebook context only.",
        data={"copied": True},
        status="active",
    )

    assert notebook.to_dict() == {
        "id": notebook.id,
        "title": "Research Notes",
        "system_prompt": "Answer using notebook context only.",
        "data": {"copied": True},
        "user_id": notebook.user_id,
        "connector_id": notebook.connector_id,
        "embedding_config_id": notebook.embedding_config_id,
        "status": "active",
    }


def test_allowed_notebook_statuses():
    assert ALLOWED_NOTEBOOK_STATUSES == {"pending", "processing", "active", "failed"}
