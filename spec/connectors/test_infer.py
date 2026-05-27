from types import SimpleNamespace

from app.helpers.api_helpers import build_jwt_header, generate_jwt
from app.services.llama_model_cache import llama_model_cache
from spec.factories import ConnectorFactory, UserFactory


def _headers(app, user):
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


def test_infer_local_connector_returns_llama_response(client, app, db_session, monkeypatch):
    llama_model_cache.clear()
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        connection_type="local",
        local_file_path="/tmp/model.gguf",
        data={"model_options": {"n_ctx": 1024}},
    )
    captured = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def create_chat_completion(self, **kwargs):
            captured["completion"] = kwargs
            return {
                "choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 3},
            }

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"prompt": "Say hello", "options": {"max_tokens": 8}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response"] == {
        "choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 3},
    }
    assert payload["details"]["total_tokens"] == 3
    assert payload["details"]["finish_reason"] == "stop"
    assert payload["details"]["tokens_per_second"] is not None
    assert captured["init"]["model_path"] == "/tmp/model.gguf"
    assert captured["init"]["n_ctx"] == 1024
    assert captured["init"]["n_threads"] > 0
    assert captured["init"]["n_threads_batch"] > 0
    assert captured["init"]["n_batch"] == 1024
    assert captured["init"]["no_perf"] is True
    assert captured["init"]["verbose"] is False
    assert captured["completion"] == {
        "messages": [
            {"role": "system", "content": app.state.settings.INFERENCE_SYSTEM_PROMPT},
            {"role": "user", "content": "Say hello"},
        ],
        "max_tokens": 8,
    }


def test_infer_local_connector_sets_default_max_tokens(client, app, db_session, monkeypatch):
    llama_model_cache.clear()
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/model.gguf")
    captured = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            pass

        def create_chat_completion(self, **kwargs):
            captured["completion"] = kwargs
            return {"ok": True}

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"input": "Say hello"},
    )

    assert response.status_code == 200
    assert captured["completion"]["max_tokens"] == 1024


def test_infer_local_connector_uses_metadata_model_path_and_limits(client, app, db_session, monkeypatch):
    llama_model_cache.clear()
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        connection_type="local",
        local_file_path="/tmp/column-model.gguf",
        data={
            "metadata": {
                "inference": {
                    "model": {"name": "Metadata Model", "local_file_path": "/tmp/metadata-model.gguf"},
                    "model_options": {"n_ctx": 2048},
                    "limits": {"default_output_tokens": 64},
                }
            }
        },
    )
    captured = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def create_chat_completion(self, **kwargs):
            captured["completion"] = kwargs
            return {"ok": True}

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"input": "Say hello"},
    )

    assert response.status_code == 200
    assert captured["init"]["model_path"] == "/tmp/metadata-model.gguf"
    assert captured["init"]["n_ctx"] == 2048
    assert captured["init"]["n_threads"] > 0
    assert captured["init"]["n_threads_batch"] > 0
    assert captured["init"]["n_batch"] == 1024
    assert captured["init"]["no_perf"] is True
    assert captured["init"]["verbose"] is False
    assert captured["completion"]["max_tokens"] == 64


def test_infer_local_connector_accepts_string_input_as_prompt(client, app, db_session, monkeypatch):
    llama_model_cache.clear()
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/model.gguf")

    class FakeLlama:
        def __init__(self, **kwargs):
            pass

        def create_chat_completion(self, **kwargs):
            return {"messages": kwargs["messages"]}

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"input": "Say hello"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response"] == {
        "messages": [
            {"role": "system", "content": app.state.settings.INFERENCE_SYSTEM_PROMPT},
            {"role": "user", "content": "Say hello"},
        ]
    }
    assert payload["details"]["total_tokens"] is None


def test_infer_local_connector_accepts_chat_messages(client, app, db_session, monkeypatch):
    llama_model_cache.clear()
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/model.gguf")

    class FakeLlama:
        def __init__(self, **kwargs):
            pass

        def create_chat_completion(self, **kwargs):
            return {"messages": kwargs["messages"]}

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    messages = [{"role": "user", "content": "Say hello"}]
    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"input": messages},
    )

    assert response.status_code == 200
    assert response.json()["response"] == {"messages": [{"role": "system", "content": app.state.settings.INFERENCE_SYSTEM_PROMPT}, *messages]}


def test_infer_local_connector_keeps_existing_system_message(client, app, db_session, monkeypatch):
    llama_model_cache.clear()
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/model.gguf")

    class FakeLlama:
        def __init__(self, **kwargs):
            pass

        def create_chat_completion(self, **kwargs):
            return {"messages": kwargs["messages"]}

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    messages = [
        {"role": "system", "content": "Use plain text."},
        {"role": "user", "content": "Say hello"},
    ]
    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"input": messages},
    )

    assert response.status_code == 200
    assert response.json()["response"] == {"messages": messages}


def test_infer_local_connector_reuses_cached_llama_instance(client, app, db_session, monkeypatch):
    llama_model_cache.clear()
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        connection_type="local",
        local_file_path="/tmp/model.gguf",
        data={"model_options": {"n_ctx": 1024}},
    )
    captured = {"init_count": 0, "completion_count": 0}

    class FakeLlama:
        def __init__(self, **kwargs):
            captured["init_count"] += 1

        def create_chat_completion(self, **kwargs):
            captured["completion_count"] += 1
            return {"ok": True}

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    for _ in range(2):
        response = client.post(
            f"/connectors/{connector.id}/infer",
            headers=_headers(app, user),
            json={"prompt": "Say hello"},
        )
        assert response.status_code == 200

    assert captured == {"init_count": 1, "completion_count": 2}


def test_infer_openai_connector_returns_openai_response(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        name="gpt-4.1",
        connection_type="openai",
        local_file_path=None,
        api_key="sk-secret",
    )
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured["create"] = kwargs
            return SimpleNamespace(
                model_dump=lambda mode: {
                    "id": "resp_123",
                    "status": "completed",
                    "mode": mode,
                    "usage": {
                        "input_tokens": 5,
                        "output_tokens": 7,
                        "total_tokens": 12,
                    },
                }
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setattr("app.operations.connectors.infer._openai_client_class", lambda: FakeOpenAI)

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"input": "Say hello", "options": {"max_output_tokens": 16}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response"] == {
        "id": "resp_123",
        "status": "completed",
        "mode": "json",
        "usage": {
            "input_tokens": 5,
            "output_tokens": 7,
            "total_tokens": 12,
        },
    }
    assert payload["details"]["prompt_tokens"] == 5
    assert payload["details"]["completion_tokens"] == 7
    assert payload["details"]["total_tokens"] == 12
    assert payload["details"]["tokens_per_second"] is not None
    assert captured["init"] == {"api_key": "sk-secret"}
    assert captured["create"] == {
        "model": "gpt-4.1",
        "input": "Say hello",
        "instructions": app.state.settings.INFERENCE_SYSTEM_PROMPT,
        "max_output_tokens": 16,
    }


def test_infer_openai_connector_allows_request_model_override(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        name="gpt-4.1",
        connection_type="openai",
        local_file_path=None,
        api_key="sk-secret",
    )
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured["create"] = kwargs
            return {"ok": True}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setattr("app.operations.connectors.infer._openai_client_class", lambda: FakeOpenAI)

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"input": "Say hello", "model": "gpt-4.1-mini"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == {"ok": True}
    assert captured["create"]["model"] == "gpt-4.1-mini"


def test_infer_openai_connector_uses_metadata_model_name(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        name="column-model",
        connection_type="openai",
        local_file_path=None,
        api_key="sk-secret",
        data={"metadata": {"inference": {"model": {"name": "metadata-model", "local_file_path": None}}}},
    )
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured["create"] = kwargs
            return {"ok": True}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setattr("app.operations.connectors.infer._openai_client_class", lambda: FakeOpenAI)

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"input": "Say hello"},
    )

    assert response.status_code == 200
    assert captured["create"]["model"] == "metadata-model"


def test_infer_connector_requires_visible_connector(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory()

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"prompt": "Say hello"},
    )

    assert response.status_code == 404


def test_infer_local_connector_rejects_object_input(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local")

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"input": {"role": "user", "content": "hello"}},
    )

    assert response.status_code == 422
    assert response.json()["input"] == ["invalid"]


def test_infer_local_connector_requires_gguf_model(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/model.bin")

    def fail_if_loaded():
        raise AssertionError("llama-cpp should not load non-gguf models")

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", fail_if_loaded)

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"prompt": "Say hello"},
    )

    assert response.status_code == 422
    assert response.json()["local_file_path"] == ["must be a .gguf model"]


def test_infer_local_connector_accepts_uppercase_gguf_extension(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/model.GGUF")

    class FakeLlama:
        def __init__(self, **kwargs):
            pass

        def create_chat_completion(self, **kwargs):
            return {"ok": True}

    monkeypatch.setattr("app.operations.connectors.infer._llama_class", lambda: FakeLlama)

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={"prompt": "Say hello"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == {"ok": True}


def test_infer_openai_connector_requires_input(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="openai", local_file_path=None, api_key="sk-secret")

    response = client.post(
        f"/connectors/{connector.id}/infer",
        headers=_headers(app, user),
        json={},
    )

    assert response.status_code == 422
    assert response.json()["input"] == ["required"]
