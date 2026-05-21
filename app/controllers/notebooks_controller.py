from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_active_user
from app.models.notebook import Notebook
from app.models.user import User
from app.schemas.notebook import NotebookCollection


ITEMS_PER_PAGE = 15
router = APIRouter(prefix="/notebooks", tags=["notebooks"])


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

    return {
        "records": [notebook.to_dict() for notebook in notebooks],
        "total_pages": total_pages,
        "current_page": page,
        "next_page": page + 1 if page < total_pages else None,
        "prev_page": page - 1 if page > 1 else None,
    }
