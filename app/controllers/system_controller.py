from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_admin_user
from app.helpers.api_helpers import generate_jwt
from app.models.user import User
from app.operations.system.login import Login
from app.schemas.system import LoginPayload, LoginResponse


router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(request: Request, payload: LoginPayload, session: Session = Depends(get_db)):
    cmd = Login(session=session, email=payload.email, password=payload.password)
    cmd.execute()

    if cmd.valid():
        token = generate_jwt(cmd.user.to_dict(), request.app.state.settings.SECRET_KEY)
        return {"token": token}

    return JSONResponse(status_code=422, content=cmd.payload)


def _database_config(database_uri):
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


@router.get("/system/doctor")
def doctor(
    request: Request,
    _current_user: User = Depends(require_admin_user),
):
    settings = request.app.state.settings

    return {
        "app": {
            "name": settings.APP_NAME,
            "env": settings.APP_ENV,
            "api_prefix": settings.API_PREFIX,
        },
        "database": _database_config(settings.SQLALCHEMY_DATABASE_URI),
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
