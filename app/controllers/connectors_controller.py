import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_active_user
from app.models.connector import Connector
from app.models.user import User
from app.operations.connectors.metadata import embedding_chunk_options, embedding_max_input_tokens, embedding_model_options
from app.operations.connectors.infer import Infer
from app.operations.connectors.save import Save
from app.operations.embeddings.generate_local_embeddings import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.operations.embeddings import GenerateLocalEmbeddings
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
        local_file_path=payload.local_file_path,
        embedding_local_file_path=payload.embedding_local_file_path,
        embedding_name=payload.embedding_name,
        data=payload.data,
    )
    operation.execute()
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)

    return operation.connector.to_dict()


@router.get("", response_model=ConnectorCollection)
def index(
    name: str | None = None,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    stmt = select(Connector).order_by(Connector.created_at.desc())
    if current_user.role != "admin":
        stmt = stmt.where(Connector.user_id == current_user.id)
    if name:
        stmt = stmt.where(Connector.name.ilike(f"%{name}%"))

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


@router.post("/{connector_id}/generate_embeddings")
def generate_embeddings(
    connector_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    connector = _visible_connector(session, connector_id, current_user)
    if connector is None:
        return JSONResponse(status_code=404, content={"message": "not found"})

    input_path = _save_upload_to_temp_file(file)
    try:
        chunk_size, chunk_overlap = embedding_chunk_options(connector, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP)
        operation = GenerateLocalEmbeddings(
            local_embedding_model=connector,
            input_file=input_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            model_options=embedding_model_options(connector),
            max_input_tokens=embedding_max_input_tokens(connector),
            source_name=file.filename,
        )
        operation.execute()
        if operation.invalid():
            return JSONResponse(status_code=422, content=operation.errors)

        return {"records": operation.embeddings}
    finally:
        input_path.unlink(missing_ok=True)


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
        local_file_path=payload.local_file_path,
        embedding_local_file_path=payload.embedding_local_file_path,
        embedding_name=payload.embedding_name,
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


def _save_upload_to_temp_file(file):
    suffix = Path(file.filename or "").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        file.file.seek(0)
        shutil.copyfileobj(file.file, temp_file)
        return Path(temp_file.name)
