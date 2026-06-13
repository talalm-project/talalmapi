import json
import subprocess
import zipfile
from types import SimpleNamespace

from app.operations.system import CreateBackup


class FakePaginator:
    def paginate(self, Bucket):
        return [{"Contents": [{"Key": "notebooks/example.txt"}]}]


class FakeS3Client:
    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return FakePaginator()

    def download_file(self, bucket, key, destination):
        assert bucket == "talalm-test"
        assert key == "notebooks/example.txt"
        with open(destination, "w", encoding="utf-8") as handle:
            handle.write("stored notebook")


def test_create_backup_writes_database_rustfs_models_config_and_metadata(tmp_path, monkeypatch):
    api_path = tmp_path / "talalmapi"
    root_path = tmp_path
    web_path = tmp_path / "talalmweb"
    model_path = root_path / "models" / "qwen.gguf"
    output_path = tmp_path / "backup.zip"

    api_path.mkdir()
    web_path.mkdir()
    model_path.parent.mkdir()
    model_path.write_text("model bytes", encoding="utf-8")
    (api_path / ".env").write_text("API_ENV=true\n", encoding="utf-8")
    (root_path / ".env").write_text("ROOT_ENV=true\n", encoding="utf-8")
    (web_path / ".env").write_text("WEB_ENV=true\n", encoding="utf-8")
    (api_path / "manifest-local-models.yml").write_text(
        f"""
-
  name: "Qwen"
  type: "embedding"
  path: "{model_path}"
""".strip(),
        encoding="utf-8",
    )

    settings = SimpleNamespace(
        APP_ENV="test",
        SQLALCHEMY_DATABASE_URI="postgresql+psycopg://developer:password@localhost:5432/talalm_test",
        STORAGE_S3_BUCKET="talalm-test",
        STORAGE_S3_REGION="us-east-1",
        STORAGE_S3_ENDPOINT="http://localhost:9000",
        STORAGE_S3_ACCESS_KEY_ID="rustfsadmin",
        STORAGE_S3_SECRET_ACCESS_KEY="rustfsadmin",
        STORAGE_S3_SESSION_TOKEN="",
        STORAGE_S3_SIGNATURE_VERSION="s3v4",
        STORAGE_S3_ADDRESSING_STYLE="path",
        LOCAL_MODELS_MANIFEST_PATH="manifest-local-models.yml",
    )

    def fake_run(command, check, env, stdout, stderr, text):
        assert command[:3] == ["pg_dump", "-Fc", "-f"]
        assert "-d" in command
        assert "talalm_test" in command
        assert env["PGPASSWORD"] == "password"
        dump_path = command[3]
        with open(dump_path, "w", encoding="utf-8") as handle:
            handle.write("database dump")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.chdir(api_path)
    monkeypatch.setattr("app.operations.system.create_backup.subprocess.run", fake_run)
    monkeypatch.setattr("app.storage._get_s3_client", lambda active_settings: FakeS3Client())

    operation = CreateBackup(settings, output_path)
    operation.execute()

    assert output_path.exists()
    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        assert "database/dump.pgcustom" in names
        assert "rustfs/talalm-test/notebooks/example.txt" in names
        assert "config/manifest-local-models.yml" in names
        assert "config/talalmapi.env" in names
        assert "config/root.env" in names
        assert "config/talalmweb.env" in names
        assert "models/qwen.gguf" in names
        assert "backup.json" in names

        backup_metadata = json.loads(archive.read("backup.json"))
        assert backup_metadata["app_env"] == "test"
        assert backup_metadata["database"]["database"] == "talalm_test"
        assert backup_metadata["rustfs"]["bucket"] == "talalm-test"
        assert backup_metadata["rustfs"]["object_count"] == 1
        assert backup_metadata["models"]["files"][0]["path"] == "models/qwen.gguf"
        assert backup_metadata["warnings"] == []


def test_create_backup_raises_when_pg_dump_is_missing(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        APP_ENV="test",
        SQLALCHEMY_DATABASE_URI="postgresql+psycopg://developer:password@localhost:5432/talalm_test",
    )

    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr("app.operations.system.create_backup.subprocess.run", fake_run)

    operation = CreateBackup(settings, tmp_path / "backup.zip")

    try:
        operation.execute()
    except RuntimeError as error:
        assert "pg_dump is required" in str(error)
    else:
        raise AssertionError("expected RuntimeError")
