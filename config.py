import os
import re
from pathlib import Path

import yaml


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_env_vars(value):
    if not isinstance(value, str):
        return value

    def _replace(match):
        return os.getenv(match.group(1), "")

    return _ENV_PATTERN.sub(_replace, value)


def _load_database_config():
    config_path = Path(os.getenv("DATABASE_YAML", "database.yaml"))
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    env = os.getenv("APP_ENV", "development")
    config = data.get(env, {})
    return {key: _expand_env_vars(value) for key, value in config.items()}


class Config:
    APP_NAME = os.getenv("APP_NAME", "TalaLM")
    APP_ENV = os.getenv("APP_ENV", "development")
    API_PREFIX = os.getenv("API_PREFIX", "")

    _db_config = _load_database_config()
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        _db_config.get(
            "uri",
            "postgresql+psycopg://postgres:postgres@localhost:5432/talalm_development",
        ),
    )
    SECRET_KEY = os.getenv("SECRET_KEY", "default-api-fast-secret")

    STORAGE_S3_BUCKET = os.getenv("STORAGE_S3_BUCKET", "")
    STORAGE_S3_REGION = os.getenv("STORAGE_S3_REGION", "")
    STORAGE_S3_ENDPOINT = os.getenv("STORAGE_S3_ENDPOINT", "")
    STORAGE_S3_ACCESS_KEY_ID = os.getenv("STORAGE_S3_ACCESS_KEY_ID", "")
    STORAGE_S3_SECRET_ACCESS_KEY = os.getenv("STORAGE_S3_SECRET_ACCESS_KEY", "")
    STORAGE_S3_SESSION_TOKEN = os.getenv("STORAGE_S3_SESSION_TOKEN", "")
    STORAGE_S3_PREFIX = os.getenv("STORAGE_S3_PREFIX", "")
    STORAGE_S3_PUBLIC_URL = os.getenv("STORAGE_S3_PUBLIC_URL", "")
    STORAGE_S3_PRESIGNED_EXPIRES_IN = int(os.getenv("STORAGE_S3_PRESIGNED_EXPIRES_IN", "3600"))
    STORAGE_S3_ACL = os.getenv("STORAGE_S3_ACL", "")
    STORAGE_S3_SIGNATURE_VERSION = os.getenv("STORAGE_S3_SIGNATURE_VERSION", "s3v4")
    STORAGE_S3_ADDRESSING_STYLE = os.getenv("STORAGE_S3_ADDRESSING_STYLE", "path")
    STORAGE_S3_CREATE_BUCKET = os.getenv("STORAGE_S3_CREATE_BUCKET", "false").lower() == "true"
    STORAGE_MAX_CONTENT_LENGTH_MB = int(os.getenv("STORAGE_MAX_CONTENT_LENGTH_MB", "100"))
    LOCAL_MODELS_MANIFEST_PATH = os.getenv("LOCAL_MODELS_MANIFEST_PATH", "manifest-local-models.yml")
