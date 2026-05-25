from app.helpers.api_helpers import build_jwt_header, generate_jwt
from spec.factories import ConnectorFactory, NotebookFactory, NotebookFileFactory, UserFactory


def _headers(app, user):
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


def test_dashboard_returns_research_monitoring_data(client, app, db_session):
    user = UserFactory(role="user")
    local_connector = ConnectorFactory(
        user=user,
        name="Local Research",
        connection_type="local",
        data={
            "metadata": {
                "provider": "local",
                "inference": {
                    "model": {"name": "Local Research", "local_file_path": "/tmp/research.gguf"},
                    "limits": {"context_window_tokens": 4096},
                },
                "embeddings": {
                    "model": {"name": "nomic", "local_file_path": "/tmp/nomic.gguf", "embedding_size": 768},
                    "limits": {"max_input_tokens": 512},
                    "chunking": {"chunk_size": 1536, "chunk_overlap": 153},
                },
            }
        },
    )
    openai_connector = ConnectorFactory(
        user=user,
        name="OpenAI Research",
        connection_type="openai",
        embedding_name="text-embedding-3-small",
    )
    active_notebook = NotebookFactory(user=user, connector=local_connector, title="Literature Review")
    empty_notebook = NotebookFactory(user=user, connector=openai_connector, title="Empty Notebook")
    active_file = NotebookFileFactory(notebook=active_notebook, name="Paper A", status="active", byte_size=2048)
    failed_file = NotebookFileFactory(
        notebook=active_notebook,
        name="Paper B",
        status="failed",
        error_message="embedding failed",
        byte_size=512,
    )
    queued_file = NotebookFileFactory(notebook=active_notebook, name="Paper C", status="processing", byte_size=256)
    other_user = UserFactory(role="user")
    other_connector = ConnectorFactory(user=other_user)
    other_notebook = NotebookFactory(user=other_user, connector=other_connector)
    NotebookFileFactory(notebook=other_notebook, status="active")

    response = client.get("/dashboard", headers=_headers(app, user))

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {
        "notebooks_count": 2,
        "active_notebooks_count": 0,
        "connectors_count": 2,
        "local_connectors_count": 1,
        "openai_connectors_count": 1,
        "active_files_count": 1,
        "queued_files_count": 1,
        "failed_files_count": 1,
        "notebooks_without_files_count": 1,
        "total_file_bytes": 2816,
        "needs_attention_count": 3,
    }
    assert [row["notebook"]["title"] for row in payload["notebooks"]] == ["Empty Notebook", "Literature Review"]
    review_row = next(row for row in payload["notebooks"] if row["notebook"]["id"] == active_notebook.id)
    assert review_row["health"] == "failed"
    assert review_row["file_summary"] == {"active": 1, "queued": 1, "failed": 1, "total": 3}
    assert review_row["connector"]["id"] == local_connector.id
    assert payload["connectors"][0]["connector"]["id"] in {local_connector.id, openai_connector.id}
    assert next(row for row in payload["connectors"] if row["connector"]["id"] == local_connector.id)["notebooks_count"] == 1
    assert [file["id"] for file in payload["attention_files"]] == [failed_file.id, queued_file.id]
    assert payload["attention_files"][0]["notebook"]["title"] == "Literature Review"
    assert active_file.id not in [file["id"] for file in payload["attention_files"]]


def test_dashboard_requires_authentication(client, app, db_session):
    response = client.get("/dashboard")

    assert response.status_code == 401
    assert response.json()["detail"] == "authentication required"
