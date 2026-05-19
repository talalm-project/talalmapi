from fastapi import APIRouter, File, Form, Request, UploadFile

from app.schemas.upload import UploadResponse
from app.storage import store_file


router = APIRouter()


@router.post("/uploads", response_model=UploadResponse, status_code=201)
def create_upload(request: Request, file: UploadFile = File(...), filename: str | None = Form(default=None)):
    result = store_file(file, request.app.state.settings, filename=filename)
    return {"file": result}
