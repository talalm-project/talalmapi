from struct import pack


def test_local_models_requires_authentication(client):
    response = client.get("/system/local_models")

    assert response.status_code == 401


def test_local_models_returns_manifest_content_for_authenticated_user(client, app, user_auth_headers, tmp_path):
    manifest_path = tmp_path / "manifest-local-models.yml"
    manifest_path.write_text(
        """
-
  name: "Mistral 3.5"
  type: "inference"
  path: "models/mistral.gguf"
-
  name: "Llama"
  type: "embeddings"
  path: "models/llama.gguf"
-
  name: "Qwen Embedding"
  type: "embedding"
  path: "models/qwen-embedding.gguf"
""".strip(),
        encoding="utf-8",
    )
    app.state.settings.LOCAL_MODELS_MANIFEST_PATH = str(manifest_path)

    response = client.get("/system/local_models", headers=user_auth_headers)

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "Mistral 3.5",
            "type": "inference",
            "path": "models/mistral.gguf",
            "context_window_min": 512,
            "context_window_max": 4096,
            "context_window_recommended": 4096,
        },
        {
            "name": "Llama",
            "type": "embeddings",
            "path": "models/llama.gguf",
            "context_window_min": None,
            "context_window_max": None,
            "context_window_recommended": None,
        },
        {
            "name": "Qwen Embedding",
            "type": "embedding",
            "path": "models/qwen-embedding.gguf",
            "context_window_min": None,
            "context_window_max": None,
            "context_window_recommended": None,
        },
    ]


def test_local_models_only_returns_supported_model_types(client, app, user_auth_headers, tmp_path):
    manifest_path = tmp_path / "manifest-local-models.yml"
    manifest_path.write_text(
        """
-
  name: "Invalid"
  type: "reranker"
  path: "models/reranker.gguf"
""".strip(),
        encoding="utf-8",
    )
    app.state.settings.LOCAL_MODELS_MANIFEST_PATH = str(manifest_path)

    response = client.get("/system/local_models", headers=user_auth_headers)

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "Invalid",
            "type": None,
            "path": "models/reranker.gguf",
            "context_window_min": None,
            "context_window_max": None,
            "context_window_recommended": None,
        },
    ]


def test_local_models_reports_gguf_context_window_as_max(client, app, user_auth_headers, tmp_path):
    models_path = tmp_path / "models"
    models_path.mkdir()
    model_path = models_path / "mistral.gguf"
    _write_gguf_metadata(model_path, {"mistral.context_length": 32768})
    manifest_path = tmp_path / "manifest-local-models.yml"
    manifest_path.write_text(
        """
-
  name: "Mistral"
  type: "inference"
  path: "models/mistral.gguf"
""".strip(),
        encoding="utf-8",
    )
    app.state.settings.LOCAL_MODELS_MANIFEST_PATH = str(manifest_path)

    response = client.get("/system/local_models", headers=user_auth_headers)

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "Mistral",
            "type": "inference",
            "path": "models/mistral.gguf",
            "context_window_min": 512,
            "context_window_max": 32768,
            "context_window_recommended": 4096,
        }
    ]


def test_local_models_returns_empty_list_when_manifest_is_missing(client, app, user_auth_headers, tmp_path):
    app.state.settings.LOCAL_MODELS_MANIFEST_PATH = str(tmp_path / "missing.yml")

    response = client.get("/system/local_models", headers=user_auth_headers)

    assert response.status_code == 200
    assert response.json() == []


def _write_gguf_metadata(path, records):
    data = bytearray()
    data.extend(b"GGUF")
    data.extend(pack("<I", 3))
    data.extend(pack("<Q", 0))
    data.extend(pack("<Q", len(records)))
    for key, value in records.items():
        encoded_key = key.encode("utf-8")
        data.extend(pack("<Q", len(encoded_key)))
        data.extend(encoded_key)
        data.extend(pack("<I", 4))
        data.extend(pack("<I", value))
    path.write_bytes(data)
