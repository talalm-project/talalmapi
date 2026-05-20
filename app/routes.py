from fastapi import APIRouter, FastAPI

from app.controllers.connectors_controller import router as connectors_router
from app.controllers.health_controller import router as health_router
from app.controllers.system_controller import router as system_router
from app.controllers.uploads_controller import router as uploads_router
from app.controllers.users_controller import router as users_router


def register_routes(app: FastAPI):
    api_router = APIRouter(prefix=app.state.settings.API_PREFIX)
    api_router.include_router(health_router)
    api_router.include_router(system_router)
    api_router.include_router(connectors_router)
    api_router.include_router(users_router)
    api_router.include_router(uploads_router)
    app.include_router(api_router)
