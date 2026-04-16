from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ..models.api_models import (
    LiveAlertsResponse,
    LiveAlertPulseResponse,
    LiveBlockingHistoryResponse,
    LiveEventsResponse,
    LiveInterfaceInfo,
    LiveInterfacesResponse,
    LiveLogsResponse,
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


@router.get("/live/events", response_model=LiveEventsResponse)
def get_live_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> LiveEventsResponse:
    services = request.app.state.services
    return services.live_runtime_service.get_recent_events(limit=limit)


@router.get("/live/alerts", response_model=LiveAlertsResponse)
def get_live_alerts(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> LiveAlertsResponse:
    services = request.app.state.services
    return services.live_runtime_service.get_recent_alerts(limit=limit)


@router.get("/live/alerts/recent", response_model=LiveAlertPulseResponse)
def get_live_alert_pulse(
    request: Request,
    since: str | None = Query(default=None),
) -> LiveAlertPulseResponse:
    services = request.app.state.services
    return services.live_runtime_service.get_recent_alert_pulse(since=since)


@router.get("/live/blocking", response_model=LiveBlockingHistoryResponse)
def get_live_blocking_history(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> LiveBlockingHistoryResponse:
    services = request.app.state.services
    return services.live_runtime_service.get_recent_blocking_events(limit=limit)


@router.get("/live/logs", response_model=LiveLogsResponse)
def get_live_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> LiveLogsResponse:
    services = request.app.state.services
    return services.live_runtime_service.get_recent_logs(limit=limit)
