from sqlalchemy.engine import make_url


class Doctor:
    def __init__(self, settings):
        self.settings = settings
        self.payload = {}

    def execute(self):
        settings = self.settings
        self.payload = {
            "app": {
                "name": settings.APP_NAME,
                "env": settings.APP_ENV,
                "api_prefix": settings.API_PREFIX,
            },
            "database": self._database_config(settings.SQLALCHEMY_DATABASE_URI),
            "storage": {
                "max_content_length_mb": settings.STORAGE_MAX_CONTENT_LENGTH_MB,
                "s3": {
                    "bucket": settings.STORAGE_S3_BUCKET,
                    "region": settings.STORAGE_S3_REGION,
                    "endpoint": settings.STORAGE_S3_ENDPOINT,
                    "prefix": settings.STORAGE_S3_PREFIX,
                    "public_url": settings.STORAGE_S3_PUBLIC_URL,
                    "presigned_expires_in": settings.STORAGE_S3_PRESIGNED_EXPIRES_IN,
                    "acl": settings.STORAGE_S3_ACL,
                    "signature_version": settings.STORAGE_S3_SIGNATURE_VERSION,
                    "addressing_style": settings.STORAGE_S3_ADDRESSING_STYLE,
                    "create_bucket": settings.STORAGE_S3_CREATE_BUCKET,
                    "access_key_configured": bool(settings.STORAGE_S3_ACCESS_KEY_ID),
                    "secret_key_configured": bool(settings.STORAGE_S3_SECRET_ACCESS_KEY),
                    "session_token_configured": bool(settings.STORAGE_S3_SESSION_TOKEN),
                },
            },
        }

    def to_dict(self):
        return self.payload

    def _database_config(self, database_uri):
        if not database_uri:
            return {"configured": False}

        url = make_url(database_uri)
        return {
            "configured": True,
            "driver": url.drivername,
            "host": url.host,
            "port": url.port,
            "database": url.database,
        }
