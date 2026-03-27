from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.api_models import BlockingMode, HealthResponse
from ..utils.time_utils import utc_now_iso


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    services = request.app.state.services
    settings = services.settings
    dataset_paths_available = {
        split: path.exists() for split, path in settings.dataset_paths.items()
    }
    return HealthResponse(
        status="ok",
        model_status=services.model_service.get_status(),
        metadata_status=services.schema_service.get_status(),
        dataset_paths_available=dataset_paths_available,
        blocking_mode=BlockingMode(settings.blocking_mode),
        timestamp=utc_now_iso(),
    )
