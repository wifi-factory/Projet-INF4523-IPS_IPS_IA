from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.api_models import ReplayRunRequest, ReplayStatusResponse


router = APIRouter(tags=["replay"])


@router.post("/replay/run", response_model=ReplayStatusResponse)
def run_replay(
    payload: ReplayRunRequest,
    request: Request,
) -> ReplayStatusResponse:
    services = request.app.state.services
    return services.replay_service.run(payload)


@router.get("/replay/status", response_model=ReplayStatusResponse)
def get_replay_status(request: Request) -> ReplayStatusResponse:
    services = request.app.state.services
    return services.replay_service.get_status()
