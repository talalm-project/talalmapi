import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.engine import make_url


class CreateBackup:
    def __init__(self, settings, output_path):
        self.settings = settings
        self.output_path = Path(output_path)
        self.payload = {}
        self.warnings = []

    def execute(self):
        if not self.output_path:
            raise ValueError("output_path is required")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="talalm-backup-") as tmp_dir:
            staging_path = Path(tmp_dir)
            database_payload = self._backup_database(staging_path)
            rustfs_payload = self._backup_rustfs(staging_path)
            config_payload = self._backup_config(staging_path)
            models_payload = self._backup_models(staging_path)

            self.payload = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "app_env": self.settings.APP_ENV,
                "database": database_payload,
                "rustfs": rustfs_payload,
                "config": config_payload,
                "models": models_payload,
                "warnings": self.warnings,
            }
            self._write_json(staging_path / "backup.json", self.payload)
            self._zip_staging_path(staging_path)

    def to_dict(self):
        return {
            "output_path": str(self.output_path),
            "warnings": self.warnings,
            **self.payload,
        }

    def _backup_database(self, staging_path):
        database_path = staging_path / "database"
        database_path.mkdir(parents=True, exist_ok=True)

        url = make_url(self.settings.SQLALCHEMY_DATABASE_URI)
        if url.get_backend_name() == "sqlite":
            return self._backup_sqlite_database(url, database_path)

        dump_path = database_path / "dump.pgcustom"
        command, env = self._pg_dump_command(url, dump_path)
        try:
            subprocess.run(command, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError as error:
            raise RuntimeError("pg_dump is required to create PostgreSQL backups.") from error
        except subprocess.CalledProcessError as error:
            message = error.stderr.strip() or error.stdout.strip() or str(error)
            raise RuntimeError(f"pg_dump failed: {message}") from error

        return {
            "type": "postgresql",
            "format": "custom",
            "path": "database/dump.pgcustom",
            "database": url.database,
            "host": url.host,
            "port": url.port,
            "driver": url.drivername,
        }

    def _backup_sqlite_database(self, url, database_path):
        if not url.database or url.database == ":memory:":
            self.warnings.append("SQLite in-memory database was not backed up.")
            return {"type": "sqlite", "path": None}

        source_path = Path(url.database)
        if not source_path.is_absolute():
            source_path = Path.cwd() / source_path

        if not source_path.exists():
            self.warnings.append(f"SQLite database file does not exist: {source_path}")
            return {"type": "sqlite", "path": None}

        destination_path = database_path / source_path.name
        shutil.copy2(source_path, destination_path)
        return {"type": "sqlite", "path": f"database/{source_path.name}"}

    def _pg_dump_command(self, url, dump_path):
        command = ["pg_dump", "-Fc", "-f", str(dump_path)]
        if url.host:
            command.extend(["-h", url.host])
        if url.port:
            command.extend(["-p", str(url.port)])
        if url.username:
            command.extend(["-U", url.username])
        if not url.database:
            raise RuntimeError("Database name is missing from SQLALCHEMY_DATABASE_URI.")
        command.extend(["-d", url.database])

        env = os.environ.copy()
        if url.password:
            env["PGPASSWORD"] = url.password
        return command, env

    def _backup_rustfs(self, staging_path):
        bucket = self.settings.STORAGE_S3_BUCKET
        if not bucket:
            self.warnings.append("STORAGE_S3_BUCKET is not configured; RustFS backup skipped.")
            return {"bucket": None, "object_count": 0}

        from app.storage import _get_s3_client

        client = _get_s3_client(self.settings)
        rustfs_path = staging_path / "rustfs" / bucket
        rustfs_path.mkdir(parents=True, exist_ok=True)

        object_count = 0
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for item in page.get("Contents", []):
                key = item["Key"]
                destination_path = rustfs_path / key
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                client.download_file(bucket, key, str(destination_path))
                object_count += 1

        return {
            "bucket": bucket,
            "object_count": object_count,
            "path": f"rustfs/{bucket}",
        }

    def _backup_config(self, staging_path):
        config_path = staging_path / "config"
        config_path.mkdir(parents=True, exist_ok=True)

        copied = []
        for source_path, archive_name in self._config_sources():
            if not source_path.exists():
                continue

            destination_path = config_path / archive_name
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
            copied.append(f"config/{archive_name}")

        if not copied:
            self.warnings.append("No local config files were found to include in the backup.")

        return {"files": copied}

    def _config_sources(self):
        cwd = Path.cwd()
        manifest_path = Path(self.settings.LOCAL_MODELS_MANIFEST_PATH)
        if not manifest_path.is_absolute():
            manifest_path = cwd / manifest_path

        sources = [
            (manifest_path, "manifest-local-models.yml"),
            (cwd / ".env", "talalmapi.env"),
            (cwd.parent / ".env", "root.env"),
            (cwd.parent / "talalmweb" / ".env", "talalmweb.env"),
        ]

        seen = set()
        unique_sources = []
        for source_path, archive_name in sources:
            resolved = source_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            unique_sources.append((source_path, archive_name))
        return unique_sources

    def _backup_models(self, staging_path):
        manifest_path = Path(self.settings.LOCAL_MODELS_MANIFEST_PATH)
        if not manifest_path.is_absolute():
            manifest_path = Path.cwd() / manifest_path

        if not manifest_path.exists():
            self.warnings.append(f"Local models manifest does not exist: {manifest_path}")
            return {"files": []}

        records = self._load_manifest_records(manifest_path)
        models_path = staging_path / "models"
        copied = []
        seen = set()

        for record in records:
            model_path = self._resolve_model_path(manifest_path, record.get("path"))
            if model_path is None:
                continue

            resolved = model_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)

            if not model_path.exists():
                self.warnings.append(f"Model file does not exist: {model_path}")
                continue

            destination_path = models_path / model_path.name
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(model_path, destination_path)
            copied.append(
                {
                    "name": record.get("name"),
                    "source_path": str(model_path),
                    "path": f"models/{model_path.name}",
                }
            )

        return {"files": copied}

    def _load_manifest_records(self, manifest_path):
        with manifest_path.open("r", encoding="utf-8") as handle:
            records = yaml.safe_load(handle) or []

        if not isinstance(records, list):
            self.warnings.append(f"Local models manifest is not a list: {manifest_path}")
            return []

        return [record for record in records if isinstance(record, dict)]

    def _resolve_model_path(self, manifest_path, raw_path):
        if not raw_path:
            self.warnings.append("Local model manifest record is missing path.")
            return None

        model_path = Path(raw_path)
        if model_path.is_absolute():
            return model_path
        return manifest_path.parent / model_path

    def _write_json(self, path, payload):
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _zip_staging_path(self, staging_path):
        with zipfile.ZipFile(self.output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging_path.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging_path))
