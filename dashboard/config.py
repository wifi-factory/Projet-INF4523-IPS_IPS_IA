from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def _read_float(name: str, default: float, *, minimum: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


@dataclass(frozen=True)
class DashboardSettings:
    project_root: Path
    backend_base_url: str
    request_timeout_seconds: float
    refresh_seconds: int
    alert_pulse_refresh_seconds: int
    events_limit: int
    alerts_limit: int
    blocking_limit: int
    logs_limit: int
    app_title: str = "IPS IA"
    app_subtitle: str = "Console live"
    course_sigle: str = "INF4523"

    @property
    def dashboard_root(self) -> Path:
        return self.project_root / "dashboard"

    @property
    def assets_dir(self) -> Path:
        return self.dashboard_root / "assets"


def build_dashboard_settings() -> DashboardSettings:
    return DashboardSettings(
        project_root=PROJECT_ROOT,
        backend_base_url=os.getenv("IPS_DASHBOARD_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/"),
        request_timeout_seconds=_read_float(
            "IPS_DASHBOARD_REQUEST_TIMEOUT_SECONDS",
            5.0,
            minimum=1.0,
        ),
        refresh_seconds=_read_int(
            "IPS_DASHBOARD_REFRESH_SECONDS",
            3,
            minimum=1,
        ),
        alert_pulse_refresh_seconds=_read_int(
            "IPS_DASHBOARD_ALERT_PULSE_REFRESH_SECONDS",
            1,
            minimum=1,
        ),
        events_limit=_read_int("IPS_DASHBOARD_EVENTS_LIMIT", 250, minimum=10),
        alerts_limit=_read_int("IPS_DASHBOARD_ALERTS_LIMIT", 150, minimum=10),
        blocking_limit=_read_int("IPS_DASHBOARD_BLOCKING_LIMIT", 150, minimum=10),
        logs_limit=_read_int("IPS_DASHBOARD_LOGS_LIMIT", 250, minimum=10),
    )


@lru_cache(maxsize=1)
def get_dashboard_settings() -> DashboardSettings:
    return build_dashboard_settings()
