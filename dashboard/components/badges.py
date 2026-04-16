from __future__ import annotations

from html import escape
from typing import Any

from dashboard.utils.formatage import (
    humanize_label,
    humanize_runtime_status,
    humanize_severity,
)


def _badge_html(text: str, variant: str) -> str:
    return f"<span class='badge badge--{variant}'>{escape(text)}</span>"


def backend_badge_html(ok: bool) -> str:
    return _badge_html(f"Backend status : {'OK' if ok else 'NOK'}", "ok" if ok else "danger")


def runtime_badge_html(status: Any) -> str:
    normalized = humanize_runtime_status(status)
    variant = "ok" if normalized == "RUNNING" else "neutral" if normalized == "STOPPED" else "warning"
    if normalized == "ERROR":
        variant = "danger"
    return _badge_html(f"Runtime : {normalized}", variant)


def label_badge_html(label: Any) -> str:
    normalized = humanize_label(label)
    variant = "success" if normalized == "Normal" else "warning"
    return _badge_html(normalized, variant)


def severity_badge_html(severity: Any) -> str:
    normalized = humanize_severity(severity)
    mapping = {
        "Critique": "critical",
        "Elevee": "warning",
        "Moyenne": "info",
        "Faible": "success",
        "Normale": "neutral",
        "Info": "info",
    }
    return _badge_html(normalized, mapping.get(normalized, "neutral"))
