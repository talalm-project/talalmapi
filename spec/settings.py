import os

os.environ.setdefault("APP_ENV", "test")

from config import Config, _load_database_config  # noqa: E402


_db_config = _load_database_config()


class TestConfig(Config):
    APP_ENV = "test"
    SQLALCHEMY_DATABASE_URI = _db_config.get(
        "uri",
        "postgresql+psycopg://postgres:postgres@localhost:5432/talalm_test",
    )
    SECRET_KEY = "test-secret-32-bytes-minimum-key"
    STORAGE_S3_BUCKET = os.getenv("STORAGE_S3_BUCKET") or "talalm-test"
    STORAGE_S3_REGION = os.getenv("STORAGE_S3_REGION") or "us-east-1"
    STORAGE_S3_ENDPOINT = os.getenv("STORAGE_S3_ENDPOINT") or "http://localhost:9000"
    STORAGE_S3_ACCESS_KEY_ID = os.getenv("STORAGE_S3_ACCESS_KEY_ID") or "rustfsadmin"
    STORAGE_S3_SECRET_ACCESS_KEY = os.getenv("STORAGE_S3_SECRET_ACCESS_KEY") or "rustfsadmin"
    STORAGE_S3_SESSION_TOKEN = os.getenv("STORAGE_S3_SESSION_TOKEN", "")
    STORAGE_S3_PREFIX = os.getenv("STORAGE_S3_PREFIX", "")
    STORAGE_S3_PUBLIC_URL = os.getenv("STORAGE_S3_PUBLIC_URL") or "http://localhost:9000/talalm-test"
    STORAGE_S3_PRESIGNED_EXPIRES_IN = int(os.getenv("STORAGE_S3_PRESIGNED_EXPIRES_IN", "3600"))
    STORAGE_S3_ACL = os.getenv("STORAGE_S3_ACL", "")
    STORAGE_S3_SIGNATURE_VERSION = os.getenv("STORAGE_S3_SIGNATURE_VERSION", "s3v4")
    STORAGE_S3_ADDRESSING_STYLE = os.getenv("STORAGE_S3_ADDRESSING_STYLE", "path")
    STORAGE_S3_CREATE_BUCKET = os.getenv("STORAGE_S3_CREATE_BUCKET", "false").lower() == "true"
