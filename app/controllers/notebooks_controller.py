from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_active_user
from app.models.embedding_config import EmbeddingConfig
from app.models.notebook import Notebook
from app.models.notebook_vector import NotebookVector
from app.models.user import User
from app.operations.embedding_configs import Resolve as ResolveEmbeddingConfig
from app.operations.notebooks import Save
from app.schemas.notebook import NotebookCollection, NotebookCreate, NotebookOut


ITEMS_PER_PAGE = 15
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
    page = max(page, 1)
    filters = [Notebook.user_id == current_user.id]

    if query:
        pattern = f"%{query}%"
        filters.append(
            or_(
                Notebook.title.ilike(pattern),
                Notebook.status.ilike(pattern),
            )
        )
    if title:
        filters.append(Notebook.title.ilike(f"%{title}%"))
    if status:
        filters.append(Notebook.status == status)

    count_stmt = select(func.count()).select_from(Notebook)
    notebooks_stmt = select(Notebook).order_by(Notebook.created_at.desc())
    for entry in filters:
        count_stmt = count_stmt.where(entry)
        notebooks_stmt = notebooks_stmt.where(entry)

    total = session.scalar(count_stmt) or 0
    total_pages = max((total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE, 1)
    notebooks = (
        session.execute(
            notebooks_stmt.offset((page - 1) * ITEMS_PER_PAGE).limit(ITEMS_PER_PAGE)
        )
        .scalars()
        .all()
        if total > 0
        else []
    )
    _ensure_embedding_configs(session, notebooks)

    return {
        "records": [notebook.to_dict() for notebook in notebooks],
        "total_pages": total_pages,
        "current_page": page,
        "next_page": page + 1 if page < total_pages else None,
        "prev_page": page - 1 if page > 1 else None,
    }


@router.get("/{notebook_id}", response_model=NotebookOut)
def show(
    notebook_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    notebook = session.get(Notebook, notebook_id)
    if notebook is None or notebook.user_id != current_user.id:
        return JSONResponse(status_code=404, content={"message": "not found"})

    _ensure_embedding_configs(session, [notebook])
    return notebook.to_dict(include_connector=True)


@router.delete("/{notebook_id}")
def delete(
    notebook_id: str,
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    notebook = session.get(Notebook, notebook_id)
    if notebook is None or (current_user.role != "admin" and notebook.user_id != current_user.id):
        return JSONResponse(status_code=404, content={"message": "not found"})

    embedding_config_id = notebook.embedding_config_id
    session.execute(sql_delete(NotebookVector).where(NotebookVector.notebook_id == notebook.id))
    session.delete(notebook)
    session.flush()

    if embedding_config_id is not None and _embedding_config_unused(session, embedding_config_id):
        embedding_config = session.get(EmbeddingConfig, embedding_config_id)
        if embedding_config is not None:
            session.delete(embedding_config)

    session.commit()
    return {"message": "ok"}


def _ensure_embedding_configs(session, notebooks):
    changed = False
    for notebook in notebooks:
        if notebook.embedding_config_id is not None:
            continue

        operation = ResolveEmbeddingConfig(session=session, connector=notebook.connector)
        operation.execute()
        if operation.invalid():
            continue

        notebook.embedding_config_id = operation.embedding_config.id
        changed = True

    if changed:
        session.commit()
        for notebook in notebooks:
            session.refresh(notebook)


def _embedding_config_unused(session, embedding_config_id):
    notebook_count = (
        session.scalar(select(func.count()).select_from(Notebook).where(Notebook.embedding_config_id == embedding_config_id))
        or 0
    )
    if notebook_count > 0:
        return False

    vector_count = (
        session.scalar(
            select(func.count()).select_from(NotebookVector).where(NotebookVector.embedding_config_id == embedding_config_id)
        )
        or 0
    )
    return vector_count == 0
