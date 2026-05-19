from types import SimpleNamespace

from app.cli import build_parser, run_services_create_bucket, run_system_seed
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


def test_namespaced_commands_use_colon_separator():
    parser = build_parser()

    assert parser.parse_args(["system:greet"]).command == "system:greet"
    assert parser.parse_args(["db:migrate"]).command == "db:migrate"
    assert parser.parse_args(["db:downgrade"]).command == "db:downgrade"
    assert parser.parse_args(["db:history"]).command == "db:history"
    assert parser.parse_args(["db:current"]).command == "db:current"
    assert parser.parse_args(
        ["users:create-admin", "--email", "admin@example.com", "--password", "password"]
    ).command == "users:create-admin"
