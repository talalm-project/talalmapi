def test_local_models_requires_authentication(client):
    response = client.get("/system/local_models")

    assert response.status_code == 401


def test_local_models_returns_manifest_content_for_authenticated_user(client, app, user_auth_headers, tmp_path):
    manifest_path = tmp_path / "manifest-local-models.yml"
    manifest_path.write_text(
        """
-
  name: "Mistral 3.5"
  path: "models/mistral.gguf"
-
  name: "Llama"
  path: "models/llama.gguf"
""".strip(),
        encoding="utf-8",
    )
    app.state.settings.LOCAL_MODELS_MANIFEST_PATH = str(manifest_path)

    response = client.get("/system/local_models", headers=user_auth_headers)

    assert response.status_code == 200
    assert response.json() == [
        {"name": "Mistral 3.5", "path": "models/mistral.gguf"},
        {"name": "Llama", "path": "models/llama.gguf"},
    ]


def test_local_models_returns_empty_list_when_manifest_is_missing(client, app, user_auth_headers, tmp_path):
    app.state.settings.LOCAL_MODELS_MANIFEST_PATH = str(tmp_path / "missing.yml")

    response = client.get("/system/local_models", headers=user_auth_headers)

    assert response.status_code == 200
    assert response.json() == []
