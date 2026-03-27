from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.api_models import BlockingDecisionResponse, BlockingEvaluationRequest
from ..utils.dataframe_utils import pick_confidence


router = APIRouter(tags=["blocking"])


@router.post("/blocking/evaluate", response_model=BlockingDecisionResponse)
def evaluate_blocking(
    payload: BlockingEvaluationRequest,
    request: Request,
) -> BlockingDecisionResponse:
    services = request.app.state.services
    confidence = payload.confidence
    if confidence is None:
        confidence = pick_confidence(payload.probability, payload.predicted_label)
    return services.blocking_service.evaluate(
        predicted_label=payload.predicted_label,
        confidence=confidence,
        operational_metadata=payload.operational_metadata,
        flow_features=payload.flow_features,
        blocking_mode=payload.blocking_mode.value if payload.blocking_mode else None,
    )
