from types import SimpleNamespace

from app.helpers.api_helpers import build_jwt_header, generate_jwt
from app.models.embedding_config import EmbeddingConfig
from app.models.notebook import DEFAULT_NOTEBOOK_SYSTEM_PROMPT, Notebook
from app.models.notebook_file import NotebookFile
from app.models.notebook_note import NotebookNote
from app.models.notebook_vector import NotebookVector
from spec.factories import (
    ConnectorFactory,
    NotebookFactory,
    NotebookFileFactory,
    NotebookNoteFactory,
    NotebookVectorFactory,
    UserFactory,
)


def _headers(app, user):
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


def test_create_notebook_assigns_current_user_and_copies_connector_data(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        data={
            "metadata": {
                "provider": "local",
                "inference": {"model": {"name": "Local Llama"}},
                "embeddings": {
                    "model": {
                        "name": "Local Embedding",
                        "local_file_path": "/tmp/local-embedding.gguf",
                        "embedding_size": 384,
                    },
                    "model_options": {"n_ctx": 2048},
                },
            }
        },
    )

    response = client.post(
        "/notebooks",
        headers=_headers(app, user),
        json={
            "title": "Contract Research",
            "system_prompt": "Use the contract documents as the source of truth.",
            "connector_id": connector.id,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Contract Research"
    assert payload["system_prompt"] == "Use the contract documents as the source of truth."
    assert payload["user_id"] == user.id
    assert payload["connector_id"] == connector.id
    assert payload["embedding_config_id"]
    assert payload["status"] == "active"
    assert payload["data"] == {"connector": connector.data}

    notebook = db_session.get(Notebook, payload["id"])
    embedding_config = db_session.get(EmbeddingConfig, payload["embedding_config_id"])
    assert notebook.user_id == user.id
    assert notebook.system_prompt == "Use the contract documents as the source of truth."
    assert notebook.connector_id == connector.id
    assert notebook.embedding_config_id == embedding_config.id
    assert notebook.data == {"connector": connector.data}
    assert notebook.status == "active"
    assert embedding_config.connector_id == connector.id
    assert embedding_config.provider == "local"
    assert embedding_config.model_name == "Local Embedding"
    assert embedding_config.model_path == "/tmp/local-embedding.gguf"
    assert embedding_config.dimensions == 384
    assert embedding_config.options == {"n_ctx": 2048}


def test_create_notebook_uses_default_system_prompt_when_blank(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)

    response = client.post(
        "/notebooks",
        headers=_headers(app, user),
        json={
            "title": "Blank Prompt",
            "system_prompt": "   ",
            "connector_id": connector.id,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["system_prompt"] == DEFAULT_NOTEBOOK_SYSTEM_PROMPT
    assert db_session.get(Notebook, payload["id"]).system_prompt == DEFAULT_NOTEBOOK_SYSTEM_PROMPT


def test_create_notebook_reuses_existing_embedding_config(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        embedding_name="text-embedding-3-small",
        data={
            "metadata": {
                "provider": "openai",
                "embeddings": {
                    "model": {
                        "name": "text-embedding-3-small",
                        "local_file_path": None,
                        "embedding_size": 1536,
                    },
                    "model_options": {},
                },
            }
        },
    )

    first_response = client.post(
        "/notebooks",
        headers=_headers(app, user),
        json={"title": "First", "connector_id": connector.id},
    )
    second_response = client.post(
        "/notebooks",
        headers=_headers(app, user),
        json={"title": "Second", "connector_id": connector.id},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["embedding_config_id"] == second_response.json()["embedding_config_id"]
    assert db_session.query(EmbeddingConfig).count() == 1


def test_create_notebook_requires_title(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)

    response = client.post(
        "/notebooks",
        headers=_headers(app, user),
        json={"connector_id": connector.id},
    )

    assert response.status_code == 422
    assert response.json()["title"] == ["required"]


def test_create_notebook_requires_connector_id(client, app, db_session):
    user = UserFactory(role="user")

    response = client.post(
        "/notebooks",
        headers=_headers(app, user),
        json={"title": "Missing Connector"},
    )

    assert response.status_code == 422
    assert response.json()["connector_id"] == ["required"]


def test_create_notebook_rejects_other_users_connector(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory()

    response = client.post(
        "/notebooks",
        headers=_headers(app, user),
        json={
            "title": "Wrong Connector",
            "connector_id": connector.id,
        },
    )

    assert response.status_code == 422
    assert response.json()["connector_id"] == ["not found"]


def test_list_notebooks_only_returns_current_users_notebooks(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    owned = NotebookFactory(user=user, connector=connector, title="Owned Notebook")
    NotebookFileFactory(notebook=owned)
    NotebookFileFactory(notebook=owned)
    NotebookFactory(title="Other Notebook")

    response = client.get("/notebooks", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json()["records"] == [
        {
            "id": owned.id,
            "title": "Owned Notebook",
            "system_prompt": DEFAULT_NOTEBOOK_SYSTEM_PROMPT,
            "data": {},
            "user_id": user.id,
            "connector_id": connector.id,
            "embedding_config_id": owned.embedding_config_id,
            "status": "active",
            "files_count": 2,
        }
    ]


def test_list_notebooks_is_paginated_to_fifteen_per_page(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    notebooks = [
        NotebookFactory(user=user, connector=connector, title=f"Notebook {index}")
        for index in range(16)
    ]

    response = client.get("/notebooks", headers=_headers(app, user))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["records"]) == 15
    assert payload["total_pages"] == 2
    assert payload["current_page"] == 1
    assert payload["next_page"] == 2
    assert payload["prev_page"] is None
    assert payload["records"][0]["id"] == notebooks[-1].id


def test_list_notebooks_returns_requested_page(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    notebooks = [
        NotebookFactory(user=user, connector=connector, title=f"Notebook {index}")
        for index in range(16)
    ]

    response = client.get("/notebooks?page=2", headers=_headers(app, user))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["records"]) == 1
    assert payload["records"][0]["id"] == notebooks[0].id
    assert payload["total_pages"] == 2
    assert payload["current_page"] == 2
    assert payload["next_page"] is None
    assert payload["prev_page"] == 1


def test_list_notebooks_searches_by_title_or_status(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    title_match = NotebookFactory(
        user=user,
        connector=connector,
        title="Planning Notes",
        status="pending",
    )
    status_match = NotebookFactory(user=user, connector=connector, title="Archive", status="active")
    NotebookFactory(user=user, connector=connector, title="Scratch", status="pending")
    NotebookFactory(title="Planning Notes", status="active")

    response = client.get("/notebooks?query=active", headers=_headers(app, user))

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [status_match.id]

    response = client.get("/notebooks?query=planning", headers=_headers(app, user))

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [title_match.id]


def test_list_notebooks_filters_by_title(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    match = NotebookFactory(user=user, connector=connector, title="Research Notebook")
    NotebookFactory(user=user, connector=connector, title="Scratch")

    response = client.get("/notebooks?title=research", headers=_headers(app, user))

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [match.id]


def test_list_notebooks_filters_by_status(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    match = NotebookFactory(user=user, connector=connector, title="Active Notebook", status="active")
    NotebookFactory(user=user, connector=connector, title="Pending Notebook", status="pending")

    response = client.get("/notebooks?status=active", headers=_headers(app, user))

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [match.id]


def test_show_notebook_allows_owner(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    notebook = NotebookFactory(
        user=user,
        connector=connector,
        title="Owned Notebook",
        system_prompt="Keep answers grounded in the notebook.",
    )

    response = client.get(f"/notebooks/{notebook.id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json() == {
        "id": notebook.id,
        "title": "Owned Notebook",
        "system_prompt": "Keep answers grounded in the notebook.",
        "data": {},
        "user_id": user.id,
        "connector_id": connector.id,
        "embedding_config_id": notebook.embedding_config_id,
        "status": "active",
        "files_count": 0,
        "connector": connector.to_dict(),
    }


def test_show_notebook_backfills_legacy_embedding_config(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    notebook = Notebook(
        title="Legacy Notebook",
        user=user,
        connector=connector,
        embedding_config_id=None,
    )
    db_session.add(notebook)
    db_session.commit()

    response = client.get(f"/notebooks/{notebook.id}", headers=_headers(app, user))

    assert response.status_code == 200
    payload = response.json()
    assert payload["embedding_config_id"]
    db_session.expire_all()
    assert db_session.get(Notebook, notebook.id).embedding_config_id == payload["embedding_config_id"]


def test_show_notebook_allows_legacy_missing_embedding_config(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, embedding_name=None, data={})
    notebook = Notebook(
        title="Incomplete Legacy Notebook",
        user=user,
        connector=connector,
        embedding_config_id=None,
    )
    db_session.add(notebook)
    db_session.commit()

    response = client.get(f"/notebooks/{notebook.id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json()["embedding_config_id"] is None


def test_update_notebook_title_allows_owner(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    notebook = NotebookFactory(user=user, connector=connector, title="Original Title")

    response = client.put(
        f"/notebooks/{notebook.id}",
        headers=_headers(app, user),
        json={"title": " Updated Research Notebook "},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == notebook.id
    assert payload["title"] == "Updated Research Notebook"
    assert payload["connector"] == connector.to_dict()
    db_session.expire_all()
    assert db_session.get(Notebook, notebook.id).title == "Updated Research Notebook"


def test_update_notebook_title_requires_title(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user, title="Original Title")

    response = client.put(
        f"/notebooks/{notebook.id}",
        headers=_headers(app, user),
        json={"title": "   "},
    )

    assert response.status_code == 422
    assert response.json()["title"] == ["required"]
    db_session.expire_all()
    assert db_session.get(Notebook, notebook.id).title == "Original Title"


def test_update_notebook_title_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(title="Other Notebook")

    response = client.put(
        f"/notebooks/{notebook.id}",
        headers=_headers(app, user),
        json={"title": "Renamed"},
    )

    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.get(Notebook, notebook.id).title == "Other Notebook"


def test_infer_notebook_uses_notebook_connector_and_system_prompt(client, app, db_session, monkeypatch):
    from app.services.llama_model_cache import llama_model_cache

    llama_model_cache.clear()
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/model.gguf")
    notebook = NotebookFactory(
        user=user,
        connector=connector,
        system_prompt="Answer only from this notebook.",
    )
    captured = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def create_chat_completion(self, **kwargs):
            captured["completion"] = kwargs
            return {
                "choices": [{"message": {"role": "assistant", "content": "notebook answer"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 4},
            }

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    response = client.post(
        f"/notebooks/{notebook.id}/infer",
        headers=_headers(app, user),
        json={"prompt": "Summarize", "options": {"max_tokens": 16}},
    )

    assert response.status_code == 200
    assert response.json()["response"] == {
        "choices": [{"message": {"role": "assistant", "content": "notebook answer"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 4},
    }
    assert captured["init"]["model_path"] == "/tmp/model.gguf"
    assert captured["init"]["n_ctx"] == 4096
    assert captured["init"]["no_perf"] is True
    assert captured["init"]["verbose"] is False
    assert captured["completion"] == {
        "messages": [
            {
                "role": "user",
                "content": (
                    "Instructions:\n\nAnswer only from this notebook.\n\nNotebook context:\n\n"
                    "No relevant notebook context was retrieved.\n\nUser question:\n\nSummarize"
                ),
            },
        ],
        "max_tokens": 16,
    }


def test_infer_notebook_uses_system_prompt_as_openai_instructions(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        name="gpt-4.1",
        connection_type="openai",
        local_file_path=None,
        api_key="sk-secret",
    )
    notebook = NotebookFactory(
        user=user,
        connector=connector,
        system_prompt="Use notebook context before general knowledge.",
    )
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured["create"] = kwargs
            return SimpleNamespace(
                model_dump=lambda mode: {
                    "id": "resp_notebook",
                    "status": "completed",
                    "mode": mode,
                }
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setattr("app.operations.connectors.infer._openai_client_class", lambda: FakeOpenAI)

    response = client.post(
        f"/notebooks/{notebook.id}/infer",
        headers=_headers(app, user),
        json={"input": "Summarize"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == {
        "id": "resp_notebook",
        "status": "completed",
        "mode": "json",
    }
    assert captured["init"] == {"api_key": "sk-secret"}
    assert captured["create"] == {
        "model": "gpt-4.1",
        "input": "Notebook context:\n\nNo relevant notebook context was retrieved.\n\nUser question:\n\nSummarize",
        "instructions": "Use notebook context before general knowledge.",
    }


def test_infer_notebook_retrieves_top_k_context(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/model.gguf")
    notebook = NotebookFactory(user=user, connector=connector)
    notebook_file = NotebookFileFactory(
        notebook=notebook,
        name="MobileNet Paper",
        filename="mobilenet.pdf",
        content_type="application/pdf",
        byte_size=2048,
        data={"url": "http://localhost:9000/talalm-test/mobilenet.pdf"},
        status="active",
    )
    NotebookVectorFactory(
        notebook=notebook,
        notebook_file=notebook_file,
        embedding_config=notebook.embedding_config,
        chunk_index=1,
        text="Most relevant notebook chunk.",
        embedding=[1.0, 0.0, 0.0],
    )
    NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        chunk_index=2,
        text="Less relevant notebook chunk.",
        embedding=[0.0, 1.0, 0.0],
    )
    captured = {}

    class FakeEmbeddingLlama:
        def __init__(self, **kwargs):
            captured["embedding_init"] = kwargs

        def create_embedding(self, _input):
            return {"data": [{"embedding": [1.0, 0.0, 0.0]}]}

    class FakeInferenceLlama:
        def __init__(self, **kwargs):
            captured["inference_init"] = kwargs

        def create_chat_completion(self, **kwargs):
            captured["completion"] = kwargs
            return {"choices": [{"message": {"role": "assistant", "content": "answer"}}]}

    monkeypatch.setattr("app.operations.notebooks.generate_query_embedding._llama_class", lambda: FakeEmbeddingLlama)
    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeInferenceLlama)

    response = client.post(
        f"/notebooks/{notebook.id}/infer",
        headers=_headers(app, user),
        json={"prompt": "What is in the file?", "k": 1},
    )

    user_message = captured["completion"]["messages"][0]["content"]
    assert response.status_code == 200
    assert captured["embedding_init"] == {"model_path": connector.embedding_local_file_path, "embedding": True}
    assert "Most relevant notebook chunk." in user_message
    assert "Less relevant notebook chunk." not in user_message
    assert response.json()["sources"] == [
        {
            "id": notebook_file.id,
            "name": "MobileNet Paper",
            "filename": "mobilenet.pdf",
            "content_type": "application/pdf",
            "byte_size": 2048,
            "url": "http://localhost:9000/talalm-test/mobilenet.pdf",
        }
    ]


def test_infer_notebook_includes_context_notes(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/model.gguf")
    notebook = NotebookFactory(user=user, connector=connector)
    NotebookNoteFactory(
        notebook=notebook,
        name="Saved Response",
        data={"content": "Saved answer about MobileNet latency."},
        is_context=True,
    )
    NotebookNoteFactory(
        notebook=notebook,
        name="Ignored Response",
        data={"content": "This note is not context."},
        is_context=None,
    )
    captured = {}

    class FakeLlama:
        def __init__(self, **_kwargs):
            pass

        def create_chat_completion(self, **kwargs):
            captured["completion"] = kwargs
            return {"choices": [{"message": {"role": "assistant", "content": "answer"}}]}

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    response = client.post(
        f"/notebooks/{notebook.id}/infer",
        headers=_headers(app, user),
        json={"prompt": "What do saved notes say?"},
    )

    prompt = captured["completion"]["messages"][0]["content"]
    assert response.status_code == 200
    assert "Notebook notes context:" in prompt
    assert "[Note 1: Saved Response] Saved answer about MobileNet latency." in prompt
    assert "This note is not context." not in prompt
    assert "User question:\n\nWhat do saved notes say?" in prompt


def test_infer_notebook_contextualizes_follow_up_queries(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/model.gguf")
    notebook = NotebookFactory(user=user, connector=connector)
    NotebookVectorFactory(
        notebook=notebook,
        embedding_config=notebook.embedding_config,
        chunk_index=1,
        text="MobileNetV4 is a neural network architecture.",
        embedding=[1.0, 0.0, 0.0],
    )
    captured = {}

    class FakeEmbeddingLlama:
        def __init__(self, **_kwargs):
            pass

        def create_embedding(self, input):
            captured["embedding_input"] = input
            return {"data": [{"embedding": [1.0, 0.0, 0.0]}]}

    class FakeInferenceLlama:
        def __init__(self, **_kwargs):
            pass

        def create_chat_completion(self, **kwargs):
            captured["completion"] = kwargs
            return {"choices": [{"message": {"role": "assistant", "content": "answer"}}]}

    monkeypatch.setattr("app.operations.notebooks.generate_query_embedding._llama_class", lambda: FakeEmbeddingLlama)
    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeInferenceLlama)

    response = client.post(
        f"/notebooks/{notebook.id}/infer",
        headers=_headers(app, user),
        json={
            "input": [
                {"role": "user", "content": "Tell me about MobileNetV4"},
                {"role": "assistant", "content": "MobileNetV4 details from the notebook."},
                {"role": "user", "content": "What is the main point of the paper?"},
            ],
            "k": 1,
        },
    )

    prompt = captured["completion"]["messages"][0]["content"]
    assert response.status_code == 200
    assert "Tell me about MobileNetV4" in captured["embedding_input"]
    assert "What is the main point of the paper?" in captured["embedding_input"]
    assert "Conversation context policy:" in prompt
    assert "resolve follow-up references like 'this'" in prompt
    assert "Conversation context:" in prompt
    assert "User: Tell me about MobileNetV4" in prompt
    assert "Assistant: MobileNetV4 details from the notebook." in prompt
    assert "User question:\n\nWhat is the main point of the paper?" in prompt


def test_infer_notebook_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()

    response = client.post(
        f"/notebooks/{notebook.id}/infer",
        headers=_headers(app, user),
        json={"prompt": "Summarize"},
    )

    assert response.status_code == 404


def test_admin_can_infer_against_other_users_notebook(client, app, db_session, monkeypatch):
    admin = UserFactory(role="admin")
    notebook = NotebookFactory(system_prompt="Admin-visible prompt.")

    class FakeLlama:
        def __init__(self, **kwargs):
            pass

        def create_chat_completion(self, **kwargs):
            return {"messages": kwargs["messages"]}

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    response = client.post(
        f"/notebooks/{notebook.id}/infer",
        headers=_headers(app, admin),
        json={"prompt": "Summarize"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == {
        "messages": [
            {
                "role": "user",
                "content": (
                    "Instructions:\n\nAdmin-visible prompt.\n\nNotebook context:\n\n"
                    "No relevant notebook context was retrieved.\n\nUser question:\n\nSummarize"
                ),
            },
        ]
    }


def test_create_notebook_file_uploads_supported_file_to_rustfs(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    captured = {}

    def fake_store_file_at_key(upload, settings, key, filename=None):
        captured["upload_filename"] = upload.filename
        captured["content_type"] = upload.content_type
        captured["key"] = key
        captured["filename"] = filename
        captured["bucket"] = settings.STORAGE_S3_BUCKET
        return {
            "key": key,
            "filename": "notes.pdf",
            "content_type": "application/pdf",
            "byte_size": None,
            "url": f"http://localhost:9000/talalm-test/{key}",
        }

    monkeypatch.setattr("app.operations.notebooks.create_file.generate_object_key", lambda: "random-object-key")
    monkeypatch.setattr("app.operations.notebooks.create_file.store_file_at_key", fake_store_file_at_key)

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_files",
        headers=_headers(app, user),
        data={"name": "Research Notes"},
        files={"file": ("notes.pdf", b"hello pdf", "application/pdf")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["notebook_id"] == notebook.id
    assert payload["name"] == "Research Notes"
    assert payload["filename"] == "notes.pdf"
    assert payload["content_type"] == "application/pdf"
    assert payload["byte_size"] == 9
    assert payload["object_key"] == "random-object-key"
    assert payload["checksum"] == "9f275d73a74baf528734b92128a320df66ae66dab4935c842d8c3879d498e3f4"
    assert payload["status"] == "pending"
    assert payload["error_message"] is None
    assert payload["data"] == {"url": "http://localhost:9000/talalm-test/random-object-key"}
    assert captured == {
        "upload_filename": "notes.pdf",
        "content_type": "application/pdf",
        "key": "random-object-key",
        "filename": "notes.pdf",
        "bucket": "talalm-test",
    }

    notebook_file = db_session.get(NotebookFile, payload["id"])
    assert notebook_file.notebook_id == notebook.id
    assert notebook_file.object_key == "random-object-key"


def test_create_notebook_note_saves_structured_data(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_notes",
        headers=_headers(app, user),
        json={
            "name": "Saved Response",
            "data": {
                "blocks": [
                    {"type": "heading", "text": "Answer"},
                    {"type": "paragraph", "text": "Model response"},
                ],
                "source": "infer",
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["notebook_id"] == notebook.id
    assert payload["name"] == "Saved Response"
    assert payload["data"] == {
        "blocks": [
            {"type": "heading", "text": "Answer"},
            {"type": "paragraph", "text": "Model response"},
        ],
        "source": "infer",
    }
    assert payload["is_context"] is None

    notebook_note = db_session.get(NotebookNote, payload["id"])
    assert notebook_note.notebook_id == notebook.id
    assert notebook_note.name == "Saved Response"


def test_create_notebook_note_requires_name(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_notes",
        headers=_headers(app, user),
        json={"name": " ", "data": {"content": "Saved response"}},
    )

    assert response.status_code == 422
    assert response.json() == {"name": ["required"], "data": []}


def test_create_notebook_note_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_notes",
        headers=_headers(app, user),
        json={"name": "Saved Response", "data": {"content": "Model response"}},
    )

    assert response.status_code == 404


def test_list_notebook_notes_returns_current_users_notes(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    older = NotebookNoteFactory(notebook=notebook, name="Older", data={"content": "old"})
    newer = NotebookNoteFactory(notebook=notebook, name="Newer", data={"content": "new"})
    NotebookNoteFactory()

    response = client.get(f"/notebooks/{notebook.id}/notebook_notes", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json()["records"] == [
        newer.to_dict(),
        older.to_dict(),
    ]


def test_list_notebook_notes_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()
    NotebookNoteFactory(notebook=notebook)

    response = client.get(f"/notebooks/{notebook.id}/notebook_notes", headers=_headers(app, user))

    assert response.status_code == 404


def test_admin_can_list_notebook_notes_for_other_users_notebook(client, app, db_session):
    admin = UserFactory(role="admin")
    notebook = NotebookFactory()
    notebook_note = NotebookNoteFactory(notebook=notebook)

    response = client.get(f"/notebooks/{notebook.id}/notebook_notes", headers=_headers(app, admin))

    assert response.status_code == 200
    assert response.json()["records"] == [notebook_note.to_dict()]


def test_delete_notebook_note_allows_owner(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    notebook_note = NotebookNoteFactory(notebook=notebook)
    notebook_note_id = notebook_note.id

    response = client.delete(
        f"/notebooks/{notebook.id}/notebook_notes/{notebook_note_id}",
        headers=_headers(app, user),
    )

    assert response.status_code == 200
    assert response.json() == {"message": "ok"}
    db_session.expire_all()
    assert db_session.get(NotebookNote, notebook_note_id) is None


def test_delete_notebook_note_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()
    notebook_note = NotebookNoteFactory(notebook=notebook)

    response = client.delete(
        f"/notebooks/{notebook.id}/notebook_notes/{notebook_note.id}",
        headers=_headers(app, user),
    )

    assert response.status_code == 404
    assert db_session.get(NotebookNote, notebook_note.id) is not None


def test_delete_notebook_note_requires_note_to_belong_to_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    other_notebook = NotebookFactory(user=user)
    notebook_note = NotebookNoteFactory(notebook=other_notebook)

    response = client.delete(
        f"/notebooks/{notebook.id}/notebook_notes/{notebook_note.id}",
        headers=_headers(app, user),
    )

    assert response.status_code == 404
    assert db_session.get(NotebookNote, notebook_note.id) is not None


def test_toggle_notebook_note_context_sets_null_note_to_true(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    notebook_note = NotebookNoteFactory(notebook=notebook, is_context=None)

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_notes/{notebook_note.id}/toggle_context",
        headers=_headers(app, user),
    )

    assert response.status_code == 200
    assert response.json()["is_context"] is True
    db_session.expire_all()
    assert db_session.get(NotebookNote, notebook_note.id).is_context is True


def test_toggle_notebook_note_context_sets_true_note_to_null(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    notebook_note = NotebookNoteFactory(notebook=notebook, is_context=True)

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_notes/{notebook_note.id}/toggle_context",
        headers=_headers(app, user),
    )

    assert response.status_code == 200
    assert response.json()["is_context"] is None
    db_session.expire_all()
    assert db_session.get(NotebookNote, notebook_note.id).is_context is None


def test_toggle_notebook_note_context_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()
    notebook_note = NotebookNoteFactory(notebook=notebook)

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_notes/{notebook_note.id}/toggle_context",
        headers=_headers(app, user),
    )

    assert response.status_code == 404
    assert db_session.get(NotebookNote, notebook_note.id).is_context is None


def test_toggle_notebook_note_context_requires_note_to_belong_to_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    other_notebook = NotebookFactory(user=user)
    notebook_note = NotebookNoteFactory(notebook=other_notebook)

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_notes/{notebook_note.id}/toggle_context",
        headers=_headers(app, user),
    )

    assert response.status_code == 404
    assert db_session.get(NotebookNote, notebook_note.id).is_context is None


def test_list_notebook_files_returns_current_users_files(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    older = NotebookFileFactory(notebook=notebook, name="Older", filename="older.pdf")
    newer = NotebookFileFactory(notebook=notebook, name="Newer", filename="newer.txt")
    NotebookFileFactory()

    response = client.get(f"/notebooks/{notebook.id}/notebook_files", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json()["records"] == [
        newer.to_dict(),
        older.to_dict(),
    ]


def test_list_notebook_files_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()
    NotebookFileFactory(notebook=notebook)

    response = client.get(f"/notebooks/{notebook.id}/notebook_files", headers=_headers(app, user))

    assert response.status_code == 404


def test_admin_can_list_notebook_files_for_other_users_notebook(client, app, db_session):
    admin = UserFactory(role="admin")
    notebook = NotebookFactory()
    notebook_file = NotebookFileFactory(notebook=notebook)

    response = client.get(f"/notebooks/{notebook.id}/notebook_files", headers=_headers(app, admin))

    assert response.status_code == 200
    assert response.json()["records"] == [notebook_file.to_dict()]


def test_download_notebook_file_streams_rustfs_object(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    notebook_file = NotebookFileFactory(
        notebook=notebook,
        filename="research notes.pdf",
        content_type="application/pdf",
        byte_size=13,
        object_key="notebooks/download-key",
    )
    captured = {}

    class FakeBody:
        def iter_chunks(self):
            yield b"hello "
            yield b"rustfs!"

    def fake_get_file(settings, key):
        captured["bucket"] = settings.STORAGE_S3_BUCKET
        captured["key"] = key
        return {"Body": FakeBody()}

    monkeypatch.setattr("app.operations.notebooks.download_file.get_file", fake_get_file)

    response = client.get(
        f"/notebooks/{notebook.id}/notebook_files/{notebook_file.id}/download",
        headers=_headers(app, user),
    )

    assert response.status_code == 200
    assert response.content == b"hello rustfs!"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-length"] == "13"
    assert 'filename="research notes.pdf"' in response.headers["content-disposition"]
    assert "filename*=UTF-8''research%20notes.pdf" in response.headers["content-disposition"]
    assert captured == {"bucket": "talalm-test", "key": "notebooks/download-key"}


def test_download_notebook_file_hides_other_users_notebook(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    notebook = NotebookFactory()
    notebook_file = NotebookFileFactory(notebook=notebook)
    downloaded = {"called": False}

    monkeypatch.setattr(
        "app.operations.notebooks.download_file.get_file",
        lambda settings, key: downloaded.update({"called": True}),
    )

    response = client.get(
        f"/notebooks/{notebook.id}/notebook_files/{notebook_file.id}/download",
        headers=_headers(app, user),
    )

    assert response.status_code == 404
    assert downloaded == {"called": False}


def test_download_notebook_file_rejects_file_from_different_notebook(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    other_notebook = NotebookFactory(user=user)
    notebook_file = NotebookFileFactory(notebook=other_notebook)
    downloaded = {"called": False}

    monkeypatch.setattr(
        "app.operations.notebooks.download_file.get_file",
        lambda settings, key: downloaded.update({"called": True}),
    )

    response = client.get(
        f"/notebooks/{notebook.id}/notebook_files/{notebook_file.id}/download",
        headers=_headers(app, user),
    )

    assert response.status_code == 404
    assert downloaded == {"called": False}


def test_admin_can_download_notebook_file_for_other_users_notebook(client, app, db_session, monkeypatch):
    admin = UserFactory(role="admin")
    notebook = NotebookFactory()
    notebook_file = NotebookFileFactory(notebook=notebook, object_key="admin-download-key")
    captured = {}

    class FakeBody:
        def iter_chunks(self):
            yield b"admin file"

    monkeypatch.setattr(
        "app.operations.notebooks.download_file.get_file",
        lambda settings, key: captured.update({"bucket": settings.STORAGE_S3_BUCKET, "key": key}) or {"Body": FakeBody()},
    )

    response = client.get(
        f"/notebooks/{notebook.id}/notebook_files/{notebook_file.id}/download",
        headers=_headers(app, admin),
    )

    assert response.status_code == 200
    assert response.content == b"admin file"
    assert captured == {"bucket": "talalm-test", "key": "admin-download-key"}


def test_create_notebook_file_requires_name(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_files",
        headers=_headers(app, user),
        data={"name": " "},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["name"] == ["required"]


def test_create_notebook_file_rejects_unsupported_file_type(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_files",
        headers=_headers(app, user),
        data={"name": "Image"},
        files={"file": ("image.png", b"png", "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["file"] == ["unsupported file type"]


def test_create_notebook_file_rejects_files_larger_than_five_mb(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    stored = {"called": False}

    monkeypatch.setattr(
        "app.operations.notebooks.create_file.store_file_at_key",
        lambda upload, settings, key, filename=None: stored.update({"called": True}),
    )

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_files",
        headers=_headers(app, user),
        data={"name": "Large Notes"},
        files={"file": ("large.pdf", b"x" * (5 * 1024 * 1024 + 1), "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["file"] == ["too large"]
    assert stored == {"called": False}


def test_create_notebook_file_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_files",
        headers=_headers(app, user),
        data={"name": "Notes"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 404


def test_admin_can_create_notebook_file_for_other_users_notebook(client, app, db_session, monkeypatch):
    admin = UserFactory(role="admin")
    notebook = NotebookFactory()

    monkeypatch.setattr("app.operations.notebooks.create_file.generate_object_key", lambda: "admin-object-key")
    monkeypatch.setattr(
        "app.operations.notebooks.create_file.store_file_at_key",
        lambda upload, settings, key, filename=None: {
            "key": key,
            "filename": filename,
            "content_type": upload.content_type,
            "byte_size": None,
            "url": f"http://localhost:9000/talalm-test/{key}",
        },
    )

    response = client.post(
        f"/notebooks/{notebook.id}/notebook_files",
        headers=_headers(app, admin),
        data={"name": "Admin Notes"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["object_key"] == "admin-object-key"


def test_delete_notebook_file_removes_rustfs_object_and_related_vectors(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    notebook_file = NotebookFileFactory(notebook=notebook, object_key="notebooks/file-key")
    vector = NotebookVectorFactory(
        notebook=notebook,
        notebook_file=notebook_file,
        embedding_config=notebook.embedding_config,
    )
    notebook_id = notebook.id
    notebook_file_id = notebook_file.id
    vector_id = vector.id
    deleted = {}

    def fake_delete_file(settings, key):
        deleted["bucket"] = settings.STORAGE_S3_BUCKET
        deleted["key"] = key

    monkeypatch.setattr("app.operations.notebooks.destroy_file.delete_file", fake_delete_file)

    response = client.delete(
        f"/notebooks/{notebook_id}/notebook_files/{notebook_file_id}",
        headers=_headers(app, user),
    )

    assert response.status_code == 200
    assert response.json() == {"message": "ok"}
    assert deleted == {"bucket": "talalm-test", "key": "notebooks/file-key"}
    db_session.expire_all()
    assert db_session.get(NotebookFile, notebook_file_id) is None
    assert db_session.get(NotebookVector, vector_id) is None
    assert db_session.get(Notebook, notebook_id) is not None


def test_delete_notebook_file_allows_active_status(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    notebook_file = NotebookFileFactory(notebook=notebook, object_key="active-file-key", status="active")
    notebook_file_id = notebook_file.id

    monkeypatch.setattr("app.operations.notebooks.destroy_file.delete_file", lambda settings, key: None)

    response = client.delete(
        f"/notebooks/{notebook.id}/notebook_files/{notebook_file.id}",
        headers=_headers(app, user),
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(NotebookFile, notebook_file_id) is None


def test_delete_notebook_file_rejects_non_deletable_status(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    notebook_file = NotebookFileFactory(notebook=notebook, object_key="processing-file-key", status="processing")
    deleted = {"called": False}

    monkeypatch.setattr(
        "app.operations.notebooks.destroy_file.delete_file",
        lambda settings, key: deleted.update({"called": True}),
    )

    response = client.delete(
        f"/notebooks/{notebook.id}/notebook_files/{notebook_file.id}",
        headers=_headers(app, user),
    )

    assert response.status_code == 422
    assert response.json()["status"] == ["cannot delete"]
    assert deleted == {"called": False}
    assert db_session.get(NotebookFile, notebook_file.id) is not None


def test_delete_notebook_file_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()
    notebook_file = NotebookFileFactory(notebook=notebook)

    response = client.delete(
        f"/notebooks/{notebook.id}/notebook_files/{notebook_file.id}",
        headers=_headers(app, user),
    )

    assert response.status_code == 404
    assert db_session.get(NotebookFile, notebook_file.id) is not None


def test_delete_notebook_file_rejects_file_from_different_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    other_notebook = NotebookFactory(user=user)
    notebook_file = NotebookFileFactory(notebook=other_notebook)

    response = client.delete(
        f"/notebooks/{notebook.id}/notebook_files/{notebook_file.id}",
        headers=_headers(app, user),
    )

    assert response.status_code == 404
    assert db_session.get(NotebookFile, notebook_file.id) is not None


def test_admin_can_delete_notebook_file_for_other_users_notebook(client, app, db_session, monkeypatch):
    admin = UserFactory(role="admin")
    notebook = NotebookFactory()
    notebook_file = NotebookFileFactory(notebook=notebook, object_key="admin-file-key")
    notebook_id = notebook.id
    notebook_file_id = notebook_file.id
    deleted = {}

    monkeypatch.setattr(
        "app.operations.notebooks.destroy_file.delete_file",
        lambda settings, key: deleted.update({"bucket": settings.STORAGE_S3_BUCKET, "key": key}),
    )

    response = client.delete(
        f"/notebooks/{notebook_id}/notebook_files/{notebook_file_id}",
        headers=_headers(app, admin),
    )

    assert response.status_code == 200
    assert deleted == {"bucket": "talalm-test", "key": "admin-file-key"}
    db_session.expire_all()
    assert db_session.get(NotebookFile, notebook_file_id) is None


def test_show_notebook_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()

    response = client.get(f"/notebooks/{notebook.id}", headers=_headers(app, user))

    assert response.status_code == 404


def test_reindex_notebook_resets_files_and_deletes_vectors(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    first_file = NotebookFileFactory(notebook=notebook, status="active", error_message="old error")
    second_file = NotebookFileFactory(notebook=notebook, status="failed", error_message="parse failed")
    first_vector = NotebookVectorFactory(
        notebook=notebook,
        notebook_file=first_file,
        embedding_config=notebook.embedding_config,
    )
    second_vector = NotebookVectorFactory(
        notebook=notebook,
        notebook_file=second_file,
        embedding_config=notebook.embedding_config,
    )
    first_file_id = first_file.id
    second_file_id = second_file.id
    first_vector_id = first_vector.id
    second_vector_id = second_vector.id

    response = client.post(f"/notebooks/{notebook.id}/reindex", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json() == {"message": "ok", "files": 2, "deleted_vectors": 2}
    db_session.expire_all()
    assert db_session.get(NotebookVector, first_vector_id) is None
    assert db_session.get(NotebookVector, second_vector_id) is None
    assert db_session.get(NotebookFile, first_file_id).status == "pending"
    assert db_session.get(NotebookFile, first_file_id).error_message is None
    assert db_session.get(NotebookFile, second_file_id).status == "pending"
    assert db_session.get(NotebookFile, second_file_id).error_message is None


def test_reindex_notebook_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()
    notebook_file = NotebookFileFactory(notebook=notebook, status="active")
    vector = NotebookVectorFactory(
        notebook=notebook,
        notebook_file=notebook_file,
        embedding_config=notebook.embedding_config,
    )

    response = client.post(f"/notebooks/{notebook.id}/reindex", headers=_headers(app, user))

    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.get(NotebookFile, notebook_file.id).status == "active"
    assert db_session.get(NotebookVector, vector.id) is not None


def test_admin_can_reindex_other_users_notebook(client, app, db_session):
    admin = UserFactory(role="admin")
    notebook = NotebookFactory()
    notebook_file = NotebookFileFactory(notebook=notebook, status="active")
    vector = NotebookVectorFactory(
        notebook=notebook,
        notebook_file=notebook_file,
        embedding_config=notebook.embedding_config,
    )
    notebook_file_id = notebook_file.id
    vector_id = vector.id

    response = client.post(f"/notebooks/{notebook.id}/reindex", headers=_headers(app, admin))

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(NotebookFile, notebook_file_id).status == "pending"
    assert db_session.get(NotebookVector, vector_id) is None


def test_delete_notebook_allows_owner_and_clears_vectors_and_unused_embedding_config(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    notebook_id = notebook.id
    embedding_config_id = notebook.embedding_config_id
    notebook_file = NotebookFileFactory(notebook=notebook)
    notebook_note = NotebookNoteFactory(notebook=notebook)
    vector = NotebookVectorFactory(notebook=notebook, embedding_config=notebook.embedding_config)
    notebook_file_id = notebook_file.id
    notebook_note_id = notebook_note.id
    vector_id = vector.id

    response = client.delete(f"/notebooks/{notebook_id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json() == {"message": "ok"}
    db_session.expire_all()
    assert db_session.get(Notebook, notebook_id) is None
    assert db_session.get(NotebookFile, notebook_file_id) is None
    assert db_session.get(NotebookNote, notebook_note_id) is None
    assert db_session.get(NotebookVector, vector_id) is None
    assert db_session.get(EmbeddingConfig, embedding_config_id) is None


def test_delete_notebook_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()

    response = client.delete(f"/notebooks/{notebook.id}", headers=_headers(app, user))

    assert response.status_code == 404
    assert db_session.get(Notebook, notebook.id) is not None


def test_admin_can_delete_other_users_notebook(client, app, db_session):
    admin = UserFactory(role="admin")
    notebook = NotebookFactory()
    notebook_id = notebook.id
    embedding_config_id = notebook.embedding_config_id

    response = client.delete(f"/notebooks/{notebook_id}", headers=_headers(app, admin))

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(Notebook, notebook_id) is None
    assert db_session.get(EmbeddingConfig, embedding_config_id) is None


def test_delete_notebook_keeps_shared_embedding_config(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    first = NotebookFactory(user=user, connector=connector)
    second = NotebookFactory(user=user, connector=connector, embedding_config=first.embedding_config)
    NotebookVectorFactory(notebook=first, embedding_config=first.embedding_config)
    first_id = first.id
    second_id = second.id
    shared_embedding_config_id = first.embedding_config_id

    response = client.delete(f"/notebooks/{first_id}", headers=_headers(app, user))

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(Notebook, first_id) is None
    assert db_session.get(Notebook, second_id) is not None
    assert db_session.get(EmbeddingConfig, shared_embedding_config_id) is not None
