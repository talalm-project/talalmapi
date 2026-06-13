from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import get_current_user, require_admin_user
from app.helpers.api_helpers import generate_jwt
from app.models.user import User
from app.operations.system import Doctor, Login
from app.schemas.system import LocalModel, LoginPayload, LoginResponse
from app.services.local_models_service import LocalModelsService


router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(request: Request, payload: LoginPayload, session: Session = Depends(get_db)):
    cmd = Login(session=session, email=payload.email, password=payload.password)
    cmd.execute()

    if cmd.valid():
        token = generate_jwt(cmd.user.to_dict(), request.app.state.settings.SECRET_KEY)
        return {"token": token}

    return JSONResponse(status_code=422, content=cmd.payload)


@router.get("/system/doctor")
def doctor(
    request: Request,
    _current_user: User = Depends(require_admin_user),
):
    operation = Doctor(request.app.state.settings)
    operation.execute()
    return operation.to_dict()


@router.get("/system/local_models", response_model=list[LocalModel])
def local_models(
    request: Request,
    _current_user: User = Depends(get_current_user),
):
    service = LocalModelsService(request.app.state.settings.LOCAL_MODELS_MANIFEST_PATH)
    return service.list()
