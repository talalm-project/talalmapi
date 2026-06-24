from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_active_user
from app.models.user import User
from app.operations.papers import (
    CreateFile,
    CreateCompileJob,
    Destroy,
    DestroyFile,
    DestroyFolder,
    Index,
    IndexCompileJobs,
    IndexFiles,
    ReadFileContent,
    Save,
    SaveFileContent,
    Show,
    ShowCompileJob,
    ShowFile,
)
from app.schemas.compile_job import CompileJobCollection, CompileJobRead
from app.schemas.paper import PaperCollection, PaperCreate, PaperRead
from app.schemas.paper_file import PaperFileCollection, PaperFileContentRead, PaperFileContentUpdate, PaperFileRead
from app.services.paper_compile_service import PaperCompileService
from app.storage import get_file


router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("", response_model=PaperCollection)
def index(
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = Index(session=session, user=current_user)
    operation.execute()
    return operation.to_dict()


@router.post("", response_model=PaperRead, status_code=201)
def create(
    payload: PaperCreate,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = Save(session=session, user=current_user, name=payload.name)
    operation.execute()
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)

    return operation.paper.to_dict()


@router.get("/{paper_id}", response_model=PaperRead)
def show(
    paper_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = Show(session=session, user=current_user, paper_id=paper_id)
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    return operation.paper.to_dict()


@router.delete("/{paper_id}")
def delete(
    request: Request,
    paper_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = Destroy(
        session=session,
        user=current_user,
        settings=request.app.state.settings,
        paper_id=paper_id,
    )
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})
    if operation.storage_errors:
        return JSONResponse(status_code=502, content={"message": "Unable to delete all paper storage objects."})

    return {"deleted": True}


@router.post("/{paper_id}/compile", response_model=CompileJobRead, status_code=201)
def compile_paper(
    request: Request,
    background_tasks: BackgroundTasks,
    paper_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = CreateCompileJob(
        session=session,
        user=current_user,
        settings=request.app.state.settings,
        paper_id=paper_id,
    )
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)

    background_tasks.add_task(PaperCompileService(request.app.state.settings).compile_job, operation.compile_job.id)
    return operation.compile_job.to_dict()


@router.get("/{paper_id}/compile-jobs", response_model=CompileJobCollection)
def index_compile_jobs(
    paper_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = IndexCompileJobs(session=session, user=current_user, paper_id=paper_id)
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    return operation.to_dict()


@router.get("/{paper_id}/compile-jobs/{job_id}", response_model=CompileJobRead)
def show_compile_job(
    paper_id: str,
    job_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = ShowCompileJob(session=session, user=current_user, paper_id=paper_id, job_id=job_id)
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    return operation.compile_job.to_dict()


@router.get("/{paper_id}/latest-pdf")
def latest_pdf(
    request: Request,
    paper_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    paper_operation = Show(session=session, user=current_user, paper_id=paper_id)
    paper_operation.execute()
    if not paper_operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    latest_job_id = (paper_operation.paper.data or {}).get("latest_compile_job_id")
    if not latest_job_id:
        return JSONResponse(status_code=404, content={"message": "not found"})

    return _compile_job_pdf_response(request, paper_operation.paper.id, latest_job_id, current_user, session)


@router.get("/{paper_id}/compile-jobs/{job_id}/pdf")
def compile_job_pdf(
    request: Request,
    paper_id: str,
    job_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    return _compile_job_pdf_response(request, paper_id, job_id, current_user, session)


@router.get("/{paper_id}/files", response_model=PaperFileCollection)
def index_files(
    paper_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = IndexFiles(session=session, user=current_user, paper_id=paper_id)
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    return operation.to_dict()


@router.delete("/{paper_id}/folders")
def delete_folder(
    request: Request,
    paper_id: str,
    path: str = Query(...),
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = DestroyFolder(
        session=session,
        user=current_user,
        settings=request.app.state.settings,
        paper_id=paper_id,
        path=path,
    )
    operation.execute()
    if operation.paper is None:
        return JSONResponse(status_code=404, content={"message": "not found"})
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})
    if operation.storage_errors:
        return JSONResponse(status_code=502, content={"message": "Unable to delete all folder storage objects."})

    return {"deleted": True, "deleted_count": operation.deleted_count}


@router.post("/{paper_id}/files/upload", response_model=PaperFileRead, status_code=201)
def upload_file(
    request: Request,
    paper_id: str,
    path: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = CreateFile(
        session=session,
        user=current_user,
        settings=request.app.state.settings,
        paper_id=paper_id,
        path=path,
        file=file,
    )
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)

    return operation.paper_file.to_dict()


@router.get("/{paper_id}/files/{file_id}", response_model=PaperFileRead)
def show_file(
    paper_id: str,
    file_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = ShowFile(session=session, user=current_user, paper_id=paper_id, paper_file_id=file_id)
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    return operation.paper_file.to_dict()


@router.get("/{paper_id}/files/{file_id}/content", response_model=PaperFileContentRead)
def show_file_content(
    request: Request,
    paper_id: str,
    file_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = ReadFileContent(
        session=session,
        user=current_user,
        settings=request.app.state.settings,
        paper_id=paper_id,
        paper_file_id=file_id,
    )
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})
    if operation.storage_error():
        return JSONResponse(status_code=502, content={"message": operation.error_message})

    return operation.to_dict()


@router.put("/{paper_id}/files/{file_id}/content", response_model=PaperFileContentRead)
def update_file_content(
    request: Request,
    paper_id: str,
    file_id: str,
    payload: PaperFileContentUpdate,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = SaveFileContent(
        session=session,
        user=current_user,
        settings=request.app.state.settings,
        paper_id=paper_id,
        paper_file_id=file_id,
        content=payload.content,
        last_known_updated_at=payload.last_known_updated_at,
    )
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})
    if operation.conflicted():
        return JSONResponse(status_code=409, content={"message": operation.conflict_message})
    if operation.invalid():
        return JSONResponse(status_code=422, content=operation.payload)
    if operation.storage_error():
        return JSONResponse(status_code=502, content={"message": operation.error_message})

    return operation.to_dict()


@router.delete("/{paper_id}/files/{file_id}")
def delete_file(
    request: Request,
    paper_id: str,
    file_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = DestroyFile(
        session=session,
        user=current_user,
        settings=request.app.state.settings,
        paper_id=paper_id,
        paper_file_id=file_id,
    )
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    return {"deleted": True}


def _compile_job_pdf_response(request, paper_id, job_id, current_user, session):
    operation = ShowCompileJob(session=session, user=current_user, paper_id=paper_id, job_id=job_id)
    operation.execute()
    if not operation.found():
        return JSONResponse(status_code=404, content={"message": "not found"})

    compile_job = operation.compile_job
    if compile_job.status != "success" or not compile_job.output_pdf_key:
        return JSONResponse(status_code=404, content={"message": "not found"})

    file_response = get_file(request.app.state.settings, compile_job.output_pdf_key)
    filename = "output.pdf"
    return StreamingResponse(
        file_response["Body"],
        media_type=file_response.get("ContentType") or "application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
        },
    )
