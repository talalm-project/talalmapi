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
            "local_file_path": "/tmp/llama.gguf",
            "embedding_local_file_path": "/tmp/nomic-embed.gguf",
            "embedding_name": "nomic-embed-text",
            "data": {"model": "llama"},
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Local Llama"
    assert payload["code"] == "local-llama"
    assert payload["user_id"] == user.id
    assert payload["embedding_local_file_path"] == "/tmp/nomic-embed.gguf"
    assert payload["embedding_name"] == "nomic-embed-text"
    assert "connection_type" not in payload
    assert payload["data"]["model"] == "llama"
    assert payload["data"]["metadata"]["schema_version"] == 1
    assert payload["data"]["metadata"]["provider"] == "local"
    assert payload["data"]["metadata"]["inference"]["model"] == {
        "name": "Local Llama",
        "local_file_path": "/tmp/llama.gguf",
    }
    assert payload["data"]["metadata"]["embeddings"]["model"] == {
        "name": "nomic-embed-text",
        "local_file_path": "/tmp/nomic-embed.gguf",
        "embedding_size": None,
    }
    assert payload["data"]["metadata"]["embeddings"]["limits"]["max_input_tokens"] == 256
    connector = db_session.get(Connector, payload["id"])
    assert connector.user_id == user.id
    assert connector.embedding_local_file_path == "/tmp/nomic-embed.gguf"
    assert connector.embedding_name == "nomic-embed-text"


def test_create_connector_requires_name(client, app, db_session):
    user = UserFactory(role="user")

    response = client.post("/connectors", headers=_headers(app, user), json={"code": "missing-name"})

    assert response.status_code == 422
    assert response.json()["name"] == ["required"]


def test_create_connector_uses_local_connection_type_internally(client, app, db_session):
    user = UserFactory(role="user")

    response = client.post("/connectors", headers=_headers(app, user), json={"code": "default", "name": "Default"})

    assert response.status_code == 201
    assert "connection_type" not in response.json()
    connector = db_session.get(Connector, response.json()["id"])
    assert connector.connection_type == "local"


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
        json={"code": "shared", "name": "Duplicate"},
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
        json={"code": "shared", "name": "Shared"},
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


def test_show_connector_allows_owner(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)

    response = client.get(f"/connectors/{connector.id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json()["id"] == connector.id
    assert "connection_type" not in response.json()


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
        json={
            "code": "updated-code",
            "name": "Updated",
            "local_file_path": None,
            "embedding_local_file_path": "/tmp/e5.gguf",
            "embedding_name": "e5-small",
            "data": {"model": "mistral"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Updated"
    assert payload["code"] == "updated-code"
    assert payload["local_file_path"] is None
    assert payload["embedding_local_file_path"] == "/tmp/e5.gguf"
    assert payload["embedding_name"] == "e5-small"
    assert payload["data"]["model"] == "mistral"
    assert payload["data"]["metadata"]["embeddings"]["model"] == {
        "name": "e5-small",
        "local_file_path": "/tmp/e5.gguf",
        "embedding_size": None,
    }


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


def test_update_connector_ignores_null_data(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, data={"model": "llama"})

    response = client.put(
        f"/connectors/{connector.id}",
        headers=_headers(app, user),
        json={"data": None},
    )

    assert response.status_code == 200
    assert response.json()["data"]["model"] == "llama"
    assert response.json()["data"]["metadata"]["provider"] == "local"
    db_session.refresh(connector)
    assert connector.data["model"] == "llama"
    assert connector.data["metadata"]["provider"] == "local"


def test_update_connector_ignores_connection_type_field(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user, connection_type="local", local_file_path="/tmp/original.gguf")

    response = client.put(
        f"/connectors/{connector.id}",
        headers=_headers(app, user),
        json={"connection_type": "remote", "local_file_path": None},
    )

    assert response.status_code == 200
    assert "connection_type" not in response.json()
    db_session.refresh(connector)
    assert connector.connection_type == "local"
    assert connector.local_file_path is None


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
