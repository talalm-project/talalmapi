from app.helpers.api_helpers import build_jwt_header, generate_jwt
from spec.factories import ConnectorFactory, UserFactory


def _headers(app, user):
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


class FakeLlama:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def create_embedding(self, input):
        return {"data": [{"embedding": [float(len(input)), 1.0]}]}


def test_generate_embeddings_local_connector_returns_records(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        connection_type="local",
        embedding_name="Qwen Embedding",
        embedding_local_file_path="/tmp/qwen-embedding.gguf",
        data={"embedding_model_options": {"n_ctx": 512}},
    )
    captured = {}

    class CapturingLlama(FakeLlama):
        def __init__(self, **kwargs):
            captured["init"] = kwargs

    monkeypatch.setattr("app.operations.embeddings.generate_local_embeddings._llama_class", lambda: CapturingLlama)

    response = client.post(
        f"/connectors/{connector.id}/generate_embeddings",
        headers=_headers(app, user),
        files={"file": ("notes.txt", b"hello embeddings", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["records"][0]["text"] == "hello embeddings"
    assert payload["records"][0]["embedding"] == [16.0, 1.0]
    assert payload["records"][0]["metadata"]["source_name"] == "notes.txt"
    assert payload["records"][0]["metadata"]["model"] == "Qwen Embedding"
    assert captured["init"] == {
        "model_path": "/tmp/qwen-embedding.gguf",
        "embedding": True,
        "n_ctx": 512,
    }


def test_generate_embeddings_local_connector_uses_metadata_options(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        connection_type="local",
        embedding_name="Qwen Embedding",
        embedding_local_file_path="/tmp/qwen-embedding.gguf",
        data={
            "metadata": {
                "embeddings": {
                    "model": {
                        "name": "Metadata Embedding",
                        "local_file_path": "/tmp/metadata-qwen-embedding.gguf",
                        "embedding_size": 1024,
                    },
                    "model_options": {"n_ctx": 2048, "n_batch": 128},
                    "limits": {"max_input_tokens": 3},
                    "chunking": {"chunk_size": 10, "chunk_overlap": 0},
                }
            }
        },
    )
    captured = {"calls": []}

    class TokenLimitedLlama:
        n_batch = 128

        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def n_ctx(self):
            return 2048

        def tokenize(self, text, add_bos=True, special=False):
            tokens = list(text)
            return ([0] if add_bos else []) + tokens

        def detokenize(self, tokens, prev_tokens=None, special=False):
            return bytes(tokens)

        def create_embedding(self, input):
            captured["calls"].append(input)
            return {"data": [{"embedding": [float(len(input))]}]}

    monkeypatch.setattr("app.operations.embeddings.generate_local_embeddings._llama_class", lambda: TokenLimitedLlama)

    response = client.post(
        f"/connectors/{connector.id}/generate_embeddings",
        headers=_headers(app, user),
        files={"file": ("notes.txt", b"abcdefghij", "text/plain")},
    )

    assert response.status_code == 200
    assert captured["init"] == {
        "model_path": "/tmp/metadata-qwen-embedding.gguf",
        "embedding": True,
        "n_ctx": 2048,
        "n_batch": 128,
    }
    assert captured["calls"] == ["ab", "cd", "ef", "gh", "ij"]
    assert response.json()["records"][0]["metadata"]["model"] == "Metadata Embedding"


def test_generate_embeddings_requires_visible_connector(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory()

    response = client.post(
        f"/connectors/{connector.id}/generate_embeddings",
        headers=_headers(app, user),
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 404


def test_generate_embeddings_rejects_unsupported_file_type(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        connection_type="local",
        embedding_name="Qwen Embedding",
        embedding_local_file_path="/tmp/qwen-embedding.gguf",
    )

    response = client.post(
        f"/connectors/{connector.id}/generate_embeddings",
        headers=_headers(app, user),
        files={"file": ("notes.csv", b"hello", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["input_file"] == ["unsupported file type"]


def test_generate_embeddings_local_connector_returns_llama_runtime_error(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        connection_type="local",
        embedding_name="Qwen Embedding",
        embedding_local_file_path="/tmp/qwen-embedding.gguf",
    )

    class FailingLlama:
        def __init__(self, **kwargs):
            pass

        def create_embedding(self, input):
            raise RuntimeError("llama_decode returned 1")

    monkeypatch.setattr("app.operations.embeddings.generate_local_embeddings._llama_class", lambda: FailingLlama)

    response = client.post(
        f"/connectors/{connector.id}/generate_embeddings",
        headers=_headers(app, user),
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["embedding"] == ["llama-cpp failed: llama_decode returned 1"]

