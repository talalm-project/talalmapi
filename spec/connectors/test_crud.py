from app.helpers.api_helpers import build_jwt_header, generate_jwt
from app.models.connector import Connector
from spec.factories import ConnectorFactory, UserFactory


def _headers(app, user):
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


def test_create_connector_assigns_current_user(client, app, db_session):
    user = UserFactory(role="user")

    response = client.post(
        "/connectors",
        headers=_headers(app, user),
        json={
            "code": "local-llama",
            "name": "Local Llama",
            "connection_type": "local",
            "local_file_path": "/tmp/llama.gguf",
            "api_key": "sk-secret",
            "data": {"model": "llama"},
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Local Llama"
    assert payload["code"] == "local-llama"
    assert payload["user_id"] == user.id
    assert "api_key" not in payload

    connector = db_session.get(Connector, payload["id"])
    assert connector.user_id == user.id
    assert connector.api_key == "sk-secret"


def test_create_connector_requires_name(client, app, db_session):
    user = UserFactory(role="user")

    response = client.post("/connectors", headers=_headers(app, user), json={"code": "missing-name", "connection_type": "local"})

    assert response.status_code == 422
    assert response.json()["name"] == ["required"]


def test_create_connector_defaults_connection_type_to_local(client, app, db_session):
    user = UserFactory(role="user")

    response = client.post("/connectors", headers=_headers(app, user), json={"code": "default", "name": "Default"})

    assert response.status_code == 201
    assert response.json()["connection_type"] == "local"


def test_create_open_ai_connector_requires_api_key(client, app, db_session):
    user = UserFactory(role="user")

    response = client.post(
        "/connectors",
        headers=_headers(app, user),
        json={"code": "gpt-4-1", "name": "gpt-4.1", "connection_type": "open-ai", "api_key": None},
    )

    assert response.status_code == 422
    assert response.json()["api_key"] == ["required"]


def test_create_connector_requires_code(client, app, db_session):
    user = UserFactory(role="user")

    response = client.post("/connectors", headers=_headers(app, user), json={"name": "No Code"})

    assert response.status_code == 422
    assert response.json()["code"] == ["required"]


def test_create_connector_requires_unique_code_per_user(client, app, db_session):
    user = UserFactory(role="user")
    other_user = UserFactory(role="user")
    ConnectorFactory(user=user, code="shared")
    ConnectorFactory(user=other_user, code="shared")

    response = client.post(
        "/connectors",
        headers=_headers(app, user),
        json={"code": "shared", "name": "Duplicate", "connection_type": "local"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == ["already taken"]


def test_create_connector_allows_same_code_for_different_users(client, app, db_session):
    user = UserFactory(role="user")
    other_user = UserFactory(role="user")
    ConnectorFactory(user=other_user, code="shared")

    response = client.post(
        "/connectors",
        headers=_headers(app, user),
        json={"code": "shared", "name": "Shared", "connection_type": "local"},
    )

    assert response.status_code == 201
    assert response.json()["code"] == "shared"


def test_list_connectors_only_returns_current_users_connectors(client, app, db_session):
    user = UserFactory(role="user")
    owned = ConnectorFactory(user=user, name="Owned")
    ConnectorFactory(name="Other")

    response = client.get("/connectors", headers=_headers(app, user))

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [owned.id]


def test_admin_list_connectors_returns_all_connectors(client, auth_headers, db_session):
    first = ConnectorFactory(name="First")
    second = ConnectorFactory(name="Second")

    response = client.get("/connectors", headers=auth_headers)

    assert response.status_code == 200
    ids = {record["id"] for record in response.json()["records"]}
    assert {first.id, second.id}.issubset(ids)


def test_list_connectors_filters_by_name(client, app, db_session):
    user = UserFactory(role="user")
    match = ConnectorFactory(user=user, name="Production Llama")
    ConnectorFactory(user=user, name="Staging Mistral")
    ConnectorFactory(name="Production Remote")

    response = client.get("/connectors?name=llama", headers=_headers(app, user))

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [match.id]


def test_list_connectors_filters_by_connection_type(client, app, db_session):
    user = UserFactory(role="user")
    match = ConnectorFactory(user=user, name="OpenAI", connection_type="open-ai", local_file_path=None)
    ConnectorFactory(user=user, name="Local", connection_type="local")
    ConnectorFactory(name="Other OpenAI", connection_type="open-ai", local_file_path=None)

    response = client.get("/connectors?connection_type=open-ai", headers=_headers(app, user))

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [match.id]


def test_list_connectors_filters_by_name_and_connection_type(client, app, db_session):
    user = UserFactory(role="user")
    match = ConnectorFactory(user=user, name="Production OpenAI", connection_type="open-ai", local_file_path=None)
    ConnectorFactory(user=user, name="Production Local", connection_type="local")
    ConnectorFactory(user=user, name="Staging OpenAI", connection_type="open-ai", local_file_path=None)

    response = client.get(
        "/connectors?name=production&connection_type=open-ai",
        headers=_headers(app, user),
    )

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [match.id]


def test_show_connector_allows_owner(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)

    response = client.get(f"/connectors/{connector.id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json()["id"] == connector.id


def test_show_connector_hides_other_users_connector(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory()

    response = client.get(f"/connectors/{connector.id}", headers=_headers(app, user))

    assert response.status_code == 404


def test_admin_can_show_other_users_connector(client, auth_headers, db_session):
    connector = ConnectorFactory()

    response = client.get(f"/connectors/{connector.id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == connector.id


def test_update_connector_allows_owner(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, name="Old")

    response = client.put(
        f"/connectors/{connector.id}",
        headers=_headers(app, user),
        json={"code": "updated-code", "name": "Updated", "local_file_path": None, "data": {"model": "mistral"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Updated"
    assert payload["code"] == "updated-code"
    assert payload["local_file_path"] is None
    assert payload["data"] == {"model": "mistral"}


def test_update_connector_blocks_other_user(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(name="Original")

    response = client.put(
        f"/connectors/{connector.id}",
        headers=_headers(app, user),
        json={"name": "Updated"},
    )

    assert response.status_code == 404
    db_session.refresh(connector)
    assert connector.name == "Original"


def test_admin_can_update_other_users_connector(client, auth_headers, db_session):
    connector = ConnectorFactory(name="Original")

    response = client.put(
        f"/connectors/{connector.id}",
        headers=auth_headers,
        json={"name": "Updated"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


def test_update_connector_rejects_duplicate_code_for_same_user(client, app, db_session):
    user = UserFactory(role="user")
    ConnectorFactory(user=user, code="taken")
    connector = ConnectorFactory(user=user, code="original")

    response = client.put(
        f"/connectors/{connector.id}",
        headers=_headers(app, user),
        json={"code": "taken"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == ["already taken"]


def test_update_open_ai_connector_rejects_null_api_key(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        name="gpt-4.1",
        connection_type="open-ai",
        local_file_path=None,
        api_key="sk-existing",
    )

    response = client.put(
        f"/connectors/{connector.id}",
        headers=_headers(app, user),
        json={"api_key": None},
    )

    assert response.status_code == 422
    assert response.json()["api_key"] == ["required"]
    db_session.refresh(connector)
    assert connector.api_key == "sk-existing"


def test_update_open_ai_connector_allows_omitted_api_key(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(
        user=user,
        name="gpt-4.1",
        connection_type="open-ai",
        local_file_path=None,
        api_key="sk-existing",
    )

    response = client.put(
        f"/connectors/{connector.id}",
        headers=_headers(app, user),
        json={"name": "gpt-4.1-mini"},
    )

    assert response.status_code == 200
    db_session.refresh(connector)
    assert connector.api_key == "sk-existing"


def test_update_local_connector_to_open_ai_requires_api_key(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", api_key=None)

    response = client.put(
        f"/connectors/{connector.id}",
        headers=_headers(app, user),
        json={"connection_type": "open-ai", "local_file_path": None},
    )

    assert response.status_code == 422
    assert response.json()["api_key"] == ["required"]


def test_delete_connector_allows_owner(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    connector_id = connector.id

    response = client.delete(f"/connectors/{connector_id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json() == {"message": "ok"}
    db_session.expire_all()
    assert db_session.get(Connector, connector_id) is None


def test_delete_connector_blocks_other_user(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory()

    response = client.delete(f"/connectors/{connector.id}", headers=_headers(app, user))

    assert response.status_code == 404
    assert db_session.get(Connector, connector.id) is not None


def test_admin_can_delete_other_users_connector(client, auth_headers, db_session):
    connector = ConnectorFactory()
    connector_id = connector.id

    response = client.delete(f"/connectors/{connector_id}", headers=auth_headers)

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.get(Connector, connector_id) is None
