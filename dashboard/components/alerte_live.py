from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

from dashboard.config import DashboardSettings, get_dashboard_settings
from dashboard.services.live_provider import fetch_recent_alert_payload
from dashboard.utils.formatage import format_score, format_timestamp


ALERT_CURSOR_KEY = "sidebar_recent_alert_cursor"
ALERT_LAST_ID_KEY = "sidebar_recent_alert_id"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _latency_ms(start_iso: str | None, end_iso: str | None) -> float | None:
    if not start_iso or not end_iso:
        return None
    try:
        start_dt = datetime.fromisoformat(start_iso)
        end_dt = datetime.fromisoformat(end_iso)
    except ValueError:
        return None
    return round((end_dt - start_dt).total_seconds() * 1000.0, 3)


def _format_latency(value: object) -> str:
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{resolved:.0f} ms"


def render_recent_alert_sidebar_panel(
    settings: DashboardSettings | None = None,
) -> None:
    resolved_settings = settings or get_dashboard_settings()
    since = st.session_state.get(ALERT_CURSOR_KEY)
    payload = fetch_recent_alert_payload(resolved_settings, since=since)

    if payload.backend_error:
        st.caption(f"Flux alertes indisponible : {payload.backend_error}")

    latest_alert = payload.latest_alert
    if latest_alert is None:
        st.markdown(
            """
            <div class="sidebar-runtime-card">
              <div class="sidebar-runtime-card__title">Derniere alerte live</div>
              <div class="sidebar-runtime-card__subtitle">En attente d'une premiere alerte.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    latest_id = str(latest_alert.get("alert_id") or "")
    previous_id = str(st.session_state.get(ALERT_LAST_ID_KEY) or "")
    is_new_alert = bool(latest_id and latest_id != previous_id and payload.new_alert_count > 0)

    cursor_value = latest_alert.get("alert_created_at") or latest_alert.get("timestamp")
    if cursor_value:
        st.session_state[ALERT_CURSOR_KEY] = str(cursor_value)
    if latest_id:
        st.session_state[ALERT_LAST_ID_KEY] = latest_id

    api_to_ui_ms = _latency_ms(payload.api_exposed_at, _now_iso())
    title = "Nouvelle alerte live" if is_new_alert else "Derniere alerte live"
    severity = str(latest_alert.get("severity") or "-").upper()
    attack_type = str(latest_alert.get("attack_type") or "-")
    src_ip = str(latest_alert.get("src_ip") or "-")
    dst_ip = str(latest_alert.get("dst_ip") or "-")
    risk_score = format_score(latest_alert.get("risk_score"))
    created_at = latest_alert.get("alert_created_at") or latest_alert.get("timestamp")

    st.markdown(
        f"""
        <div class="sidebar-runtime-card">
          <div class="sidebar-runtime-card__title">{escape(title)}</div>
          <div class="sidebar-runtime-card__subtitle">{escape(severity)} · {escape(attack_type)}</div>
          <div class="sidebar-runtime-summary">
            <div class="sidebar-runtime-summary__row">
              <span>Source</span>
              <strong class="sidebar-runtime-summary__value">{escape(src_ip)}</strong>
            </div>
            <div class="sidebar-runtime-summary__row">
              <span>Destination</span>
              <strong class="sidebar-runtime-summary__value">{escape(dst_ip)}</strong>
            </div>
            <div class="sidebar-runtime-summary__row">
              <span>Score</span>
              <strong class="sidebar-runtime-summary__value">{escape(risk_score)}</strong>
            </div>
            <div class="sidebar-runtime-summary__row">
              <span>Heure</span>
              <strong class="sidebar-runtime-summary__value">{escape(format_timestamp(created_at))}</strong>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Latence finalisation -> alerte : "
        f"{_format_latency(latest_alert.get('latency_from_finalization_ms'))} · "
        "API -> affichage : "
        f"{_format_latency(api_to_ui_ms)}"
    )
