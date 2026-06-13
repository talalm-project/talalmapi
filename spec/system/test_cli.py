from types import SimpleNamespace
import json

from app.cli import (
    build_parser,
    run_system_restore_factory_settings,
    run_services_create_bucket,
    run_system_doctor,
    run_system_seed,
    run_system_start_notebook_worker,
)
from app.helpers.api_helpers import password_match
from app.models.user import User
from spec.factories import UserFactory


def test_system_seed_creates_default_admin_user(app, db_session, capsys, monkeypatch):
    monkeypatch.setattr("app.cli._active_settings", lambda: app.state.settings)

    result = run_system_seed(SimpleNamespace())

    assert result == 0
    db_session.expire_all()
    user = db_session.query(User).filter_by(email="admin@example.com").one()
    assert user.first_name == "admin"
    assert user.last_name == "example"
    assert user.role == "admin"
    assert user.status == "active"
    assert password_match("password", user.password_hash)
    assert capsys.readouterr().out.strip() == "Admin user created: admin@example.com"


def test_system_seed_updates_existing_user_to_default_admin(app, db_session, capsys, monkeypatch):
    monkeypatch.setattr("app.cli._active_settings", lambda: app.state.settings)
    user = db_session.query(User).filter_by(email="admin@example.com").one_or_none()
    if user is None:
        user = UserFactory(
            email="admin@example.com",
            first_name="wrong",
            last_name="name",
            role="user",
            status="inactive",
        )
    else:
        user.first_name = "wrong"
        user.last_name = "name"
        user.role = "user"
        user.status = "inactive"
        db_session.commit()

    result = run_system_seed(SimpleNamespace())

    assert result == 0
    db_session.expire_all()
    user = db_session.query(User).filter_by(email="admin@example.com").one()
    assert user.first_name == "admin"
    assert user.last_name == "example"
    assert user.role == "admin"
    assert user.status == "active"
    assert password_match("password", user.password_hash)
    assert capsys.readouterr().out.strip() == "Admin user updated: admin@example.com"


def test_services_create_bucket_creates_configured_rustfs_bucket(capsys, monkeypatch):
    settings = SimpleNamespace(STORAGE_S3_BUCKET="talalm-local")

    monkeypatch.setattr("app.cli._active_settings", lambda: settings)
    monkeypatch.setattr("app.storage.ensure_bucket", lambda active_settings: True)

    result = run_services_create_bucket(SimpleNamespace())

    assert result == 0
    assert capsys.readouterr().out.strip() == "RustFS bucket created: talalm-local"


def test_services_create_bucket_reports_existing_bucket(capsys, monkeypatch):
    settings = SimpleNamespace(STORAGE_S3_BUCKET="talalm-local")

    monkeypatch.setattr("app.cli._active_settings", lambda: settings)
    monkeypatch.setattr("app.storage.ensure_bucket", lambda active_settings: False)

    result = run_services_create_bucket(SimpleNamespace())

    assert result == 0
    assert capsys.readouterr().out.strip() == "RustFS bucket already exists: talalm-local"


def test_services_create_bucket_command_is_registered():
    args = build_parser().parse_args(["services:create_bucket"])

    assert args.handler is run_services_create_bucket


def test_system_doctor_prints_sanitized_configuration(app, capsys, monkeypatch):
    monkeypatch.setattr("app.cli._active_settings", lambda: app.state.settings)

    result = run_system_doctor(SimpleNamespace())

    assert result == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["app"]["name"] == app.state.settings.APP_NAME
    assert payload["app"]["env"] == "test"
    assert payload["database"]["configured"] is True
    assert payload["storage"]["s3"]["bucket"] == "talalm-test"
    assert payload["storage"]["s3"]["access_key_configured"] is True
    assert app.state.settings.SECRET_KEY not in output


def test_system_doctor_command_is_registered():
    args = build_parser().parse_args(["system:doctor"])

    assert args.handler is run_system_doctor


def test_restore_factory_settings_drops_creates_migrates_and_seeds(app, monkeypatch):
    calls = []

    monkeypatch.setattr("app.cli._active_settings", lambda: app.state.settings)
    monkeypatch.setattr("app.cli.drop_database", lambda settings: calls.append(("drop", settings)))
    monkeypatch.setattr("app.cli.create_database", lambda settings: calls.append(("create", settings)))
    monkeypatch.setattr(
        "app.cli.run_db_upgrade",
        lambda args: calls.append(("upgrade", args.revision)) or 0,
    )
    monkeypatch.setattr(
        "app.cli.run_system_seed",
        lambda args: calls.append(("seed", args)) or 0,
    )

    result = run_system_restore_factory_settings(SimpleNamespace())

    assert result == 0
    assert calls[0] == ("drop", app.state.settings)
    assert calls[1] == ("create", app.state.settings)
    assert calls[2] == ("upgrade", "head")
    assert calls[3][0] == "seed"


def test_restore_factory_settings_stops_when_migration_fails(app, monkeypatch):
    calls = []

    monkeypatch.setattr("app.cli._active_settings", lambda: app.state.settings)
    monkeypatch.setattr("app.cli.drop_database", lambda settings: calls.append("drop"))
    monkeypatch.setattr("app.cli.create_database", lambda settings: calls.append("create"))
    monkeypatch.setattr("app.cli.run_db_upgrade", lambda args: calls.append("upgrade") or 1)
    monkeypatch.setattr("app.cli.run_system_seed", lambda args: calls.append("seed") or 0)

    result = run_system_restore_factory_settings(SimpleNamespace())

    assert result == 1
    assert calls == ["drop", "create", "upgrade"]


def test_restore_factory_settings_command_is_registered():
    args = build_parser().parse_args(["system:restore_factory_settings"])

    assert args.handler is run_system_restore_factory_settings


def test_start_notebook_worker_command_is_registered():
    args = build_parser().parse_args(["system:start_notebook_worker"])

    assert args.handler is run_system_start_notebook_worker


def test_start_notebook_worker_configures_database_and_starts_worker(app, monkeypatch):
    captured = {}

    class FakeWorker:
        def __init__(self, settings):
            captured["settings"] = settings

        def run_forever(self):
            captured["run_forever"] = True

    monkeypatch.setattr("app.cli._active_settings", lambda: app.state.settings)
    monkeypatch.setattr("app.db.db.configure", lambda database_uri: captured.update({"database_uri": database_uri}))
    monkeypatch.setattr("app.operations.notebooks.NotebookWorker", FakeWorker)

    result = run_system_start_notebook_worker(SimpleNamespace())

    assert result == 0
    assert captured["database_uri"] == app.state.settings.SQLALCHEMY_DATABASE_URI
    assert captured["settings"] == app.state.settings
    assert captured["run_forever"] is True


def test_namespaced_commands_use_colon_separator():
    parser = build_parser()

    assert parser.parse_args(["system:greet"]).command == "system:greet"
    assert parser.parse_args(["system:doctor"]).command == "system:doctor"
    assert parser.parse_args(["system:restore_factory_settings"]).command == "system:restore_factory_settings"
    assert parser.parse_args(["system:start_notebook_worker"]).command == "system:start_notebook_worker"
    assert parser.parse_args(["db:migrate"]).command == "db:migrate"
    assert parser.parse_args(["db:downgrade"]).command == "db:downgrade"
    assert parser.parse_args(["db:history"]).command == "db:history"
    assert parser.parse_args(["db:current"]).command == "db:current"
    assert parser.parse_args(
        ["users:create-admin", "--email", "admin@example.com", "--password", "password"]
    ).command == "users:create-admin"
