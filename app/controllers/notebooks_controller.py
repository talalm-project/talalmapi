from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_active_user
from app.models.user import User
from app.operations.notebooks import CreateFile, Destroy, DestroyFile, DownloadFile, Index, IndexFiles, Infer, Save, Show
from app.schemas.connector import ConnectorInfer
from app.schemas.notebook_file import NotebookFileCollection, NotebookFileOut
from app.schemas.notebook import NotebookCollection, NotebookCreate, NotebookOut


router = APIRouter(prefix="/notebooks", tags=["notebooks"])


@router.post("", response_model=NotebookOut, status_code=201)
def create(
    payload: NotebookCreate,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = Save(
        session=session,
        user=current_user,
        title=payload.title,
        system_prompt=payload.system_prompt,
        connector_id=payload.connector_id,
    )
    operation.execute()
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)

    return operation.notebook.to_dict()


@router.get("", response_model=NotebookCollection)
def index(
    query: str | None = None,
    title: str | None = None,
    status: str | None = None,
    page: int = 1,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = Index(
        session=session,
        user=current_user,
        query=query,
        title=title,
        status=status,
        page=page,
    )
    operation.execute()
    return operation.to_dict()


@router.get("/{notebook_id}", response_model=NotebookOut)
def show(
    notebook_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = Show(session=session, user=current_user, notebook_id=notebook_id)
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    return operation.notebook.to_dict(include_connector=True)


@router.post("/{notebook_id}/infer")
def infer(
    notebook_id: str,
    payload: ConnectorInfer,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = Infer(session=session, user=current_user, notebook_id=notebook_id, payload=payload)
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})
    if not operation.valid():
        return JSONResponse(status_code=422, content=operation.errors)

    return operation.response


@router.get("/{notebook_id}/notebook_files", response_model=NotebookFileCollection)
def index_notebook_files(
    notebook_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = IndexFiles(session=session, user=current_user, notebook_id=notebook_id)
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    return operation.to_dict()


@router.post("/{notebook_id}/notebook_files", response_model=NotebookFileOut, status_code=201)
def create_notebook_file(
    request: Request,
    notebook_id: str,
    name: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = CreateFile(
        session=session,
        user=current_user,
        settings=request.app.state.settings,
        notebook_id=notebook_id,
        name=name,
        file=file,
    )
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)

    return operation.notebook_file.to_dict()


@router.get("/{notebook_id}/notebook_files/{notebook_file_id}/download")
def download_notebook_file(
    request: Request,
    notebook_id: str,
    notebook_file_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = DownloadFile(
        session=session,
        user=current_user,
        settings=request.app.state.settings,
        notebook_id=notebook_id,
        notebook_file_id=notebook_file_id,
    )
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    filename = operation.notebook_file.filename
    content_type = operation.notebook_file.content_type or "application/octet-stream"
    safe_filename = filename.replace('"', "")
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{quote(filename)}',
    }
    if operation.notebook_file.byte_size is not None:
        headers["Content-Length"] = str(operation.notebook_file.byte_size)

    return StreamingResponse(
        operation.file_response["Body"].iter_chunks(),
        media_type=content_type,
        headers=headers,
    )


@router.delete("/{notebook_id}/notebook_files/{notebook_file_id}")
def delete_notebook_file(
    request: Request,
    notebook_id: str,
    notebook_file_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = DestroyFile(
        session=session,
        user=current_user,
        settings=request.app.state.settings,
        notebook_id=notebook_id,
        notebook_file_id=notebook_file_id,
    )
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)

    return {"message": "ok"}


@router.delete("/{notebook_id}")
def delete(
    notebook_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = Destroy(session=session, user=current_user, notebook_id=notebook_id)
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    return {"message": "ok"}
