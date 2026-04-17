from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.badges import backend_badge_html, runtime_badge_html
from dashboard.components.cartes import KpiCard, render_kpi_cards, render_page_header, render_panel_title
from dashboard.config import get_dashboard_settings
from dashboard.components.tableaux import render_dataframe
from dashboard.services.live_provider import fetch_overview_payload
from dashboard.utils.formatage import format_timestamp
from dashboard.utils.rafraichissement import (
    fragment_interval,
    render_background_sync_status,
    signature_changed,
)


settings = get_dashboard_settings()


@st.fragment(run_every=fragment_interval(settings.refresh_seconds))
def render_overview_live() -> None:
    payload = fetch_overview_payload(settings)
    status = payload.live_status

    header_signature = {
        "backend_ok": payload.backend_ok,
        "runtime_status": status.get("status"),
    }
    if signature_changed("overview_header_signature", header_signature):
        with OVERVIEW_HEADER_SLOT.container():
            render_page_header(
                "Vue ensemble",
                "Vue synthese du moteur et des alertes live.",
                pills=[
                    backend_badge_html(payload.backend_ok),
                    runtime_badge_html(status.get("status")),
                ],
            )

    with OVERVIEW_SYNC_SLOT.container():
        render_background_sync_status(
            scope_key="vue_ensemble",
            refresh_seconds=settings.refresh_seconds,
            backend_ok=payload.backend_ok,
        )

    error_signature = {"backend_error": payload.backend_error}
    if signature_changed("overview_error_signature", error_signature):
        if payload.backend_error:
            with OVERVIEW_ERROR_SLOT.container():
                st.error(f"Backend indisponible : {payload.backend_error}")
        else:
            OVERVIEW_ERROR_SLOT.empty()

    kpi_signature = payload.summaries
    if signature_changed("overview_kpi_signature", kpi_signature):
        with OVERVIEW_KPI_SLOT.container():
            render_kpi_cards(
                [
                    KpiCard("Flux finalises", payload.summaries["finalized_flows"], "compteur runtime", "accent"),
                    KpiCard("Alertes", payload.summaries["alerts"], "incidents ouverts", "warning"),
                    KpiCard("Blocages", payload.summaries["blocking"], "actions declenchees", "danger"),
                    KpiCard("Trafic suspect", payload.summaries["suspect_rate"], "sur predictions live", "success"),
                ]
            )

    body_signature = {
        "status": {
            "session_id": status.get("session_id"),
            "interface_name": status.get("interface_name"),
            "active_flows": status.get("active_flows"),
            "predictions": status.get("predictions"),
            "packet_parse_errors": status.get("packet_parse_errors"),
            "last_event_at": status.get("last_event_at"),
        },
        "events": payload.dataframes["events"],
        "alerts": payload.dataframes["alerts"],
    }
    if signature_changed("overview_body_signature", body_signature):
        with OVERVIEW_BODY_SLOT.container():
            left, right = st.columns([1.55, 1.0], gap="large")

            with left:
                with st.container(border=True):
                    render_panel_title("Runtime live", "Etat courant du moteur.")
                    runtime_left, runtime_right = st.columns(2, gap="large")
                    runtime_left.metric("Session", status.get("session_id") or "-")
                    runtime_right.metric("Interface", status.get("interface_name") or "-")
                    runtime_left.metric("Flux actifs", int(status.get("active_flows", 0) or 0))
                    runtime_right.metric("Predictions", int(status.get("predictions", 0) or 0))
                    runtime_left.metric("Erreurs parsing", int(status.get("packet_parse_errors", 0) or 0))
                    runtime_right.metric("Derniere alerte", format_timestamp(status.get("last_event_at")))

                with st.container(border=True):
                    render_panel_title("Evenements classes", "Flux recents classes par le moteur IA.")
                    overview_events = payload.dataframes["events"][
                        ["Heure", "Label", "Score", "Proto", "Source", "Destination", "Action"]
                    ]
                    render_dataframe(overview_events, height=320)

            with right:
                with st.container(border=True):
                    render_panel_title("Alertes recentes", "Dernieres anomalies detectees.")
                    overview_alerts = payload.dataframes["alerts"][
                        ["Heure", "Severite", "Type", "Source", "Destination", "Action"]
                    ]
                    render_dataframe(overview_alerts, height=320)

OVERVIEW_HEADER_SLOT = st.empty()
OVERVIEW_SYNC_SLOT = st.empty()
OVERVIEW_ERROR_SLOT = st.empty()
OVERVIEW_KPI_SLOT = st.empty()
OVERVIEW_BODY_SLOT = st.empty()
render_overview_live()
