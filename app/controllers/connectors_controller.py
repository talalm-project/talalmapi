from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_active_user
from app.models.connector import ALLOWED_CONNECTION_TYPES, Connector
from app.models.user import User
from app.schemas.connector import ConnectorCollection, ConnectorCreate, ConnectorOut, ConnectorUpdate


router = APIRouter(prefix="/connectors", tags=["connectors"])


def _validation_errors(payload):
    errors = {
        "name": [],
        "connection_type": [],
        "data": [],
    }

    if payload.name is not None and not payload.name.strip():
        errors["name"].append("required")
    if getattr(payload, "data", None) is not None and not isinstance(payload.data, dict):
        errors["data"].append("invalid")
    if payload.connection_type and payload.connection_type not in ALLOWED_CONNECTION_TYPES:
        errors["connection_type"].append("invalid")

    return errors


def _has_errors(errors):
    return any(errors[field] for field in errors)


def _visible_connector(session, connector_id, current_user):
    connector = session.get(Connector, connector_id)
    if connector is None:
        return None
    if current_user.role != "admin" and connector.user_id != current_user.id:
        return None
    return connector


@router.post("", response_model=ConnectorOut, status_code=201)
def create(
    payload: ConnectorCreate,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    errors = _validation_errors(payload)
    if payload.name is None:
        errors["name"].append("required")
    if _has_errors(errors):
        return JSONResponse(status_code=422, content=errors)

    connector = Connector(
        user_id=current_user.id,
        name=payload.name,
        connection_type=payload.connection_type or "local",
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
    if _has_errors(errors):
        return JSONResponse(status_code=422, content=errors)

    if hasattr(payload, "model_fields_set"):
        changed_fields = payload.model_fields_set
    else:
        changed_fields = payload.__fields_set__

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
