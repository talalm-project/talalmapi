from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_active_user
from app.models.connector import Connector
from app.models.user import User
from app.operations.connectors.infer import Infer
from app.operations.connectors.save import Save
from app.schemas.connector import ConnectorCollection, ConnectorCreate, ConnectorInfer, ConnectorOut, ConnectorUpdate


router = APIRouter(prefix="/connectors", tags=["connectors"])


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
    operation = Save(
        session=session,
        user=current_user,
        code=payload.code,
        name=payload.name,
        connection_type=payload.connection_type,
        local_file_path=payload.local_file_path,
        api_key=payload.api_key,
        data=payload.data,
    )
    operation.execute()
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)

    return operation.connector.to_dict()


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

    if hasattr(payload, "model_fields_set"):
        changed_fields = payload.model_fields_set
    else:
        changed_fields = payload.__fields_set__

    operation = Save(
        session=session,
        user=connector.user,
        connector=connector,
        code=payload.code,
        name=payload.name,
        connection_type=payload.connection_type,
        local_file_path=payload.local_file_path,
        api_key=payload.api_key,
        data=payload.data,
        changed_fields=changed_fields,
    )
    operation.execute()
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)

    return operation.connector.to_dict()


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
