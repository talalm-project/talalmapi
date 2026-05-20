from spec.factories import ConnectorFactory


def test_connector_factory_creates_connector(db_session):
    connector = ConnectorFactory(data={"model": "llama"})

    assert connector.id is not None
    assert connector.user_id == connector.user.id
    assert connector.name.startswith("Connector ")
    assert connector.connection_type == "local"
    assert connector.local_file_path.endswith(".gguf")
    assert connector.api_key is None
    assert connector.data == {"model": "llama"}
    assert connector.created_at is not None
    assert connector.updated_at is not None


def test_connector_to_dict_returns_public_fields(db_session):
    connector = ConnectorFactory(api_key="sk-secret", data={"model": "llama"})

    assert connector.to_dict() == {
        "id": connector.id,
        "user_id": connector.user_id,
        "name": connector.name,
        "connection_type": connector.connection_type,
        "local_file_path": connector.local_file_path,
        "data": {"model": "llama"},
    }
    assert "api_key" not in connector.to_dict()
