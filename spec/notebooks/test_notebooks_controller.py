from app.helpers.api_helpers import build_jwt_header, generate_jwt
from app.models.embedding_config import EmbeddingConfig
from app.models.notebook import Notebook
from app.models.notebook_vector import NotebookVector
from spec.factories import ConnectorFactory, NotebookFactory, NotebookVectorFactory, UserFactory


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
            "connector_id": connector.id,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Contract Research"
    assert payload["user_id"] == user.id
    assert payload["connector_id"] == connector.id
    assert payload["embedding_config_id"]
    assert payload["status"] == "pending"
    assert payload["data"] == {"connector": connector.data}

    notebook = db_session.get(Notebook, payload["id"])
    embedding_config = db_session.get(EmbeddingConfig, payload["embedding_config_id"])
    assert notebook.user_id == user.id
    assert notebook.connector_id == connector.id
    assert notebook.embedding_config_id == embedding_config.id
    assert notebook.data == {"connector": connector.data}
    assert notebook.status == "pending"
    assert embedding_config.connector_id == connector.id
    assert embedding_config.provider == "local"
    assert embedding_config.model_name == "Local Embedding"
    assert embedding_config.model_path == "/tmp/local-embedding.gguf"
    assert embedding_config.dimensions == 384
    assert embedding_config.options == {"n_ctx": 2048}


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
    NotebookFactory(title="Other Notebook")

    response = client.get("/notebooks", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json()["records"] == [
        {
            "id": owned.id,
            "title": "Owned Notebook",
            "data": {},
            "user_id": user.id,
            "connector_id": connector.id,
            "embedding_config_id": owned.embedding_config_id,
            "status": "pending",
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
    notebook = NotebookFactory(user=user, connector=connector, title="Owned Notebook")

    response = client.get(f"/notebooks/{notebook.id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json() == {
        "id": notebook.id,
        "title": "Owned Notebook",
        "data": {},
        "user_id": user.id,
        "connector_id": connector.id,
        "embedding_config_id": notebook.embedding_config_id,
        "status": "pending",
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


def test_show_notebook_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()

    response = client.get(f"/notebooks/{notebook.id}", headers=_headers(app, user))

    assert response.status_code == 404


def test_delete_notebook_allows_owner_and_clears_vectors_and_unused_embedding_config(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory(user=user)
    notebook_id = notebook.id
    embedding_config_id = notebook.embedding_config_id
    vector = NotebookVectorFactory(notebook=notebook, embedding_config=notebook.embedding_config)
    vector_id = vector.id

    response = client.delete(f"/notebooks/{notebook_id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json() == {"message": "ok"}
    db_session.expire_all()
    assert db_session.get(Notebook, notebook_id) is None
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
