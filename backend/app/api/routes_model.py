from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.api_models import ModelInfoResponse


router = APIRouter(tags=["model"])


@router.get("/model/info", response_model=ModelInfoResponse)
def get_model_info(request: Request) -> ModelInfoResponse:
    services = request.app.state.services
    return services.model_service.get_model_info()
