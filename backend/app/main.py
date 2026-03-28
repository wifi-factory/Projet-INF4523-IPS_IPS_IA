from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .api.routes_blocking import router as blocking_router
from .api.routes_dataset import router as dataset_router
from .api.routes_detection import router as detection_router
from .api.routes_health import router as health_router
from .api.routes_live import router as live_router
from .api.routes_model import router as model_router
from .api.routes_replay import router as replay_router
from .config import get_settings
from .core.exceptions import ApplicationError
from .core.logging import configure_logging, get_logger
from .services.container import build_service_container


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    services = build_service_container(settings)
    services.schema_service.get_contract()
    services.model_service.ensure_model_loaded()
    app.state.services = services
    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Prototype backend universitaire d'IPS IA basé sur un modèle "
            "flow-level et un blocage contrôlé post-classification."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        logger.error(
            "Application error handled",
            extra={
                "context": {
                    "path": str(request.url.path),
                    "error_type": type(exc).__name__,
                    "message": exc.message,
                }
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_type": type(exc).__name__},
        )

    app.include_router(health_router)
    app.include_router(model_router)
    app.include_router(dataset_router)
    app.include_router(detection_router)
    app.include_router(blocking_router)
    app.include_router(replay_router)
    app.include_router(live_router)
    return app


app = create_app()
