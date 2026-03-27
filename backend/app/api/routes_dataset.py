from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.api_models import DatasetSummaryResponse


router = APIRouter(tags=["datasets"])


@router.get("/datasets/summary", response_model=DatasetSummaryResponse)
def get_dataset_summary(request: Request) -> DatasetSummaryResponse:
    services = request.app.state.services
    return services.dataset_service.get_summary()
