from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import require_active_user
from app.models.user import User
from app.operations.dashboard import Show
from app.schemas.dashboard import DashboardOut


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def show(
    current_user: User = Depends(require_active_user),
    session: Session = Depends(get_db),
):
    operation = Show(session=session, user=current_user)
    operation.execute()
    return operation.payload
