from sqlalchemy.engine import make_url


def _flatten_values(value):
    if isinstance(value, dict):
        values = []
        for entry in value.values():
            values.extend(_flatten_values(entry))
        return values
    if isinstance(value, list):
        values = []
        for entry in value:
            values.extend(_flatten_values(entry))
        return values
    return [value]


def test_doctor_requires_authentication(client):
    response = client.get("/system/doctor")

    assert response.status_code == 401


def test_doctor_requires_admin_role(client, user_auth_headers):
    response = client.get("/system/doctor", headers=user_auth_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "unauthorized"


def test_doctor_returns_sanitized_configuration(client, auth_headers, app):
    response = client.get("/system/doctor", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()

    assert payload["app"] == {
        "name": app.state.settings.APP_NAME,
        "env": "test",
        "api_prefix": app.state.settings.API_PREFIX,
    }

    database_url = make_url(app.state.settings.SQLALCHEMY_DATABASE_URI)
    assert payload["database"] == {
        "configured": True,
        "driver": database_url.drivername,
        "host": database_url.host,
        "port": database_url.port,
        "database": database_url.database,
    }
    assert payload["storage"]["max_content_length_mb"] == app.state.settings.STORAGE_MAX_CONTENT_LENGTH_MB
    assert payload["storage"]["s3"]["bucket"] == "talalm-test"
    assert payload["storage"]["s3"]["access_key_configured"] is True
    assert payload["storage"]["s3"]["secret_key_configured"] is True
    assert payload["storage"]["s3"]["session_token_configured"] is False

    values = [str(value) for value in _flatten_values(payload)]
    assert app.state.settings.SECRET_KEY not in values
    assert app.state.settings.STORAGE_S3_ACCESS_KEY_ID not in values
    assert app.state.settings.STORAGE_S3_SECRET_ACCESS_KEY not in values
    assert database_url.username not in values
    assert database_url.password not in values
