from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_active_user
from app.models.connector import ALLOWED_CONNECTION_TYPES, Connector
from app.models.user import User
from app.operations.connectors.infer import Infer
from app.schemas.connector import ConnectorCollection, ConnectorCreate, ConnectorInfer, ConnectorOut, ConnectorUpdate


router = APIRouter(prefix="/connectors", tags=["connectors"])


def _validation_errors(payload):
    errors = {
        "code": [],
        "name": [],
        "connection_type": [],
        "api_key": [],
        "data": [],
    }

    if payload.code is not None and not payload.code.strip():
        errors["code"].append("required")
    if payload.name is not None and not payload.name.strip():
        errors["name"].append("required")
    if getattr(payload, "data", None) is not None and not isinstance(payload.data, dict):
        errors["data"].append("invalid")
    if payload.connection_type and payload.connection_type not in ALLOWED_CONNECTION_TYPES:
        errors["connection_type"].append("invalid")

    return errors


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _has_errors(errors):
    return any(errors[field] for field in errors)


def _visible_connector(session, connector_id, current_user):
    connector = session.get(Connector, connector_id)
    if connector is None:
        return None
    if current_user.role != "admin" and connector.user_id != current_user.id:
        return None
    return connector


def _code_taken(session, user_id, code, connector_id=None):
    stmt = select(Connector).where(Connector.user_id == user_id).where(Connector.code == code)
    if connector_id is not None:
        stmt = stmt.where(Connector.id != connector_id)
    return session.scalar(stmt) is not None


@router.post("", response_model=ConnectorOut, status_code=201)
def create(
    payload: ConnectorCreate,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    errors = _validation_errors(payload)
    if payload.code is None:
        errors["code"].append("required")
    if payload.name is None:
        errors["name"].append("required")
    connection_type = payload.connection_type or "local"
    if connection_type == "openai" and _blank(payload.api_key):
        errors["api_key"].append("required")
    code = payload.code.strip() if payload.code else None
    if code and _code_taken(session, current_user.id, code):
        errors["code"].append("already taken")
    if _has_errors(errors):
        return JSONResponse(status_code=422, content=errors)

    connector = Connector(
        user_id=current_user.id,
        code=code,
        name=payload.name,
        connection_type=connection_type,
        local_file_path=payload.local_file_path,
        api_key=payload.api_key,
        data=payload.data,
    )
    session.add(connector)
    session.commit()
    session.refresh(connector)

    return connector.to_dict()


@router.get("", response_model=ConnectorCollection)
def index(
    name: str | None = None,
    connection_type: str | None = None,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    stmt = select(Connector).order_by(Connector.created_at.desc())
    if current_user.role != "admin":
        stmt = stmt.where(Connector.user_id == current_user.id)
    if name:
        stmt = stmt.where(Connector.name.ilike(f"%{name}%"))
    if connection_type:
        stmt = stmt.where(Connector.connection_type == connection_type)

    connectors = session.execute(stmt).scalars().all()
    return {"records": [connector.to_dict() for connector in connectors]}


@router.get("/{connector_id}", response_model=ConnectorOut)
def show(
    connector_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    connector = _visible_connector(session, connector_id, current_user)
    if connector is None:
        return JSONResponse(status_code=404, content={"message": "not found"})

    return connector.to_dict()


@router.post("/{connector_id}/infer")
def infer(
    request: Request,
    connector_id: str,
    payload: ConnectorInfer,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    connector = _visible_connector(session, connector_id, current_user)
    if connector is None:
        return JSONResponse(status_code=404, content={"message": "not found"})

    operation = Infer(connector, payload, system_prompt=request.app.state.settings.INFERENCE_SYSTEM_PROMPT)
    operation.execute()
    if not operation.valid():
        return JSONResponse(status_code=422, content=operation.errors)

    return operation.response


@router.put("/{connector_id}", response_model=ConnectorOut)
def update(
    connector_id: str,
    payload: ConnectorUpdate,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    connector = _visible_connector(session, connector_id, current_user)
    if connector is None:
        return JSONResponse(status_code=404, content={"message": "not found"})

    errors = _validation_errors(payload)
    if hasattr(payload, "model_fields_set"):
        changed_fields = payload.model_fields_set
    else:
        changed_fields = payload.__fields_set__

    connection_type = payload.connection_type if payload.connection_type is not None else connector.connection_type
    api_key = payload.api_key if "api_key" in changed_fields else connector.api_key
    if connection_type == "openai" and _blank(api_key):
        errors["api_key"].append("required")
    code = payload.code.strip() if payload.code is not None else connector.code
    if payload.code is not None and code and _code_taken(session, connector.user_id, code, connector.id):
        errors["code"].append("already taken")
    if _has_errors(errors):
        return JSONResponse(status_code=422, content=errors)

    if payload.code is not None:
        connector.code = code
    if payload.name is not None:
        connector.name = payload.name
    if payload.connection_type is not None:
        connector.connection_type = payload.connection_type
    if "local_file_path" in changed_fields:
        connector.local_file_path = payload.local_file_path
    if "api_key" in changed_fields:
        connector.api_key = payload.api_key
    if payload.data is not None:
        connector.data = payload.data

    session.commit()
    session.refresh(connector)
    return connector.to_dict()


@router.delete("/{connector_id}")
def delete(
    connector_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    connector = _visible_connector(session, connector_id, current_user)
    if connector is None:
        return JSONResponse(status_code=404, content={"message": "not found"})

    session.delete(connector)
    session.commit()
    return {"message": "ok"}
