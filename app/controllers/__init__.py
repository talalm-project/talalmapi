from app.controllers.dashboard_controller import router as dashboard_router
from app.controllers.health_controller import router as health_router
from app.controllers.system_controller import router as system_router
from app.controllers.uploads_controller import router as uploads_router
from app.controllers.users_controller import router as users_router

__all__ = ["dashboard_router", "health_router", "system_router", "uploads_router", "users_router"]
