from app.helpers.api_helpers import build_jwt_header, generate_jwt
from app.models.notebook import Notebook
from spec.factories import ConnectorFactory, NotebookFactory, UserFactory


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
    assert payload["status"] == "pending"
    assert payload["data"] == {"connector": connector.data}

    notebook = db_session.get(Notebook, payload["id"])
    assert notebook.user_id == user.id
    assert notebook.connector_id == connector.id
    assert notebook.data == {"connector": connector.data}
    assert notebook.status == "pending"


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
        "status": "pending",
        "connector": connector.to_dict(),
    }


def test_show_notebook_hides_other_users_notebook(client, app, db_session):
    user = UserFactory(role="user")
    notebook = NotebookFactory()

    response = client.get(f"/notebooks/{notebook.id}", headers=_headers(app, user))

    assert response.status_code == 404
