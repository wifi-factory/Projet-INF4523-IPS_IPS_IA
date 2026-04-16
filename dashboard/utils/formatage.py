from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd


def format_compact_number(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "0"
    return f"{number:,}".replace(",", " ")


def format_percent(numerator: Any, denominator: Any) -> str:
    try:
        num = float(numerator)
        den = float(denominator)
    except (TypeError, ValueError):
        return "0,0 %"
    if den <= 0:
        return "0,0 %"
    return f"{(num / den) * 100:.1f}".replace(".", ",") + " %"


def format_score(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def format_timestamp(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        if isinstance(value, datetime):
            return value.strftime("%H:%M:%S")
        timestamp = pd.to_datetime(value, errors="coerce", utc=False)
        if pd.isna(timestamp):
            return str(value)
        return timestamp.strftime("%H:%M:%S")
    except Exception:
        return str(value)


def format_duration_seconds(value: Any) -> str:
    try:
        total = int(float(value))
    except (TypeError, ValueError):
        return "-"
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def normalize_backend_status(value: Any) -> str:
    if value in (None, ""):
        return "NOK"
    text = str(value).strip().lower()
    return "OK" if text == "ok" else "NOK"


def humanize_runtime_status(value: Any) -> str:
    mapping = {
        "running": "RUNNING",
        "stopped": "STOPPED",
        "stopping": "STOPPING",
        "error": "ERROR",
    }
    if value is None:
        return "INCONNU"
    return mapping.get(str(value).strip().lower(), str(value).upper())


def humanize_label(value: Any) -> str:
    mapping = {
        "normal": "Normal",
        "suspect": "Suspect",
    }
    if value is None:
        return "Inconnu"
    return mapping.get(str(value).strip().lower(), str(value))


def humanize_severity(value: Any) -> str:
    mapping = {
        "critical": "Critique",
        "high": "Elevee",
        "medium": "Moyenne",
        "low": "Faible",
        "normal": "Normale",
        "info": "Info",
        "warning": "Avertissement",
    }
    if value is None:
        return "Inconnue"
    return mapping.get(str(value).strip().lower(), str(value))


def humanize_action(value: Any) -> str:
    mapping = {
        "allow": "Autoriser",
        "alert_only": "Alerte",
        "block_dry_run": "Blocage",
        "block_system_stub": "Blocage",
        "block_enforce": "Blocage",
        "block": "Blocage",
        "observe": "Observation",
    }
    if value is None:
        return "-"
    return mapping.get(str(value).strip().lower(), str(value))


def humanize_event_status(value: Any) -> str:
    mapping = {
        "open": "Ouverte",
        "closed": "Fermee",
        "blocked": "Bloquee",
        "executed": "Executee",
        "simulated": "Simulee",
        "alert_only": "Alerte",
        "escalated": "Escaladee",
    }
    if value is None:
        return "-"
    return mapping.get(str(value).strip().lower(), str(value))


def protocol_label(value: Any) -> str:
    if value is None:
        return "-"
    return str(value).upper()
