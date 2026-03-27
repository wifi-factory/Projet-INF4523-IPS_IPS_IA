from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.api_models import FlowDetectionRequest, FlowDetectionResponse


router = APIRouter(tags=["detection"])


@router.post("/detect/flow", response_model=FlowDetectionResponse)
def detect_flow(
    payload: FlowDetectionRequest,
    request: Request,
) -> FlowDetectionResponse:
    services = request.app.state.services
    return services.detection_service.detect_flow(
        flow_features=payload.flow_features,
        operational_metadata=payload.operational_metadata,
        blocking_mode=payload.blocking_mode.value if payload.blocking_mode else None,
    )
