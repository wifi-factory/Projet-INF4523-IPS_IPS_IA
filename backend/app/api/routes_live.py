from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.api_models import (
    LiveInterfaceInfo,
    LiveInterfacesResponse,
    LiveStartRequest,
    LiveStatusResponse,
)


router = APIRouter(tags=["live"])


@router.get("/live/interfaces", response_model=LiveInterfacesResponse)
def get_live_interfaces(request: Request) -> LiveInterfacesResponse:
    services = request.app.state.services
    interfaces = [
        LiveInterfaceInfo(index=index, label=label)
        for index, label in services.live_capture_service.list_interfaces()
    ]
    return LiveInterfacesResponse(interfaces=interfaces)


@router.post("/live/start", response_model=LiveStatusResponse)
def start_live_monitoring(
    payload: LiveStartRequest,
    request: Request,
) -> LiveStatusResponse:
    services = request.app.state.services
    return services.live_runtime_service.start(payload)


@router.post("/live/stop", response_model=LiveStatusResponse)
def stop_live_monitoring(request: Request) -> LiveStatusResponse:
    services = request.app.state.services
    return services.live_runtime_service.stop()


@router.get("/live/status", response_model=LiveStatusResponse)
def get_live_status(request: Request) -> LiveStatusResponse:
    services = request.app.state.services
    return services.live_runtime_service.get_status()
