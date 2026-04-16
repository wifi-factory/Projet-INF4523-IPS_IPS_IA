from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.badges import backend_badge_html, runtime_badge_html
from dashboard.components.cartes import (
    KpiCard,
    render_detail_list,
    render_kpi_cards,
    render_page_header,
    render_panel_title,
)
from dashboard.config import get_dashboard_settings
from dashboard.components.tableaux import render_dataframe
from dashboard.services.live_provider import fetch_runtime_payload
from dashboard.utils.formatage import format_duration_seconds
from dashboard.utils.rafraichissement import fragment_interval, render_background_sync_status


settings = get_dashboard_settings()


@st.fragment(run_every=fragment_interval(settings.refresh_seconds))
def render_runtime_live() -> None:
    payload = fetch_runtime_payload(settings)
    status = payload.live_status

    render_page_header(
        "Runtime live",
        "Etat technique du moteur, capture active et pipeline de traitement.",
        pills=[
            backend_badge_html(payload.backend_ok),
            runtime_badge_html(status.get("status")),
        ],
    )
    render_background_sync_status(
        scope_key="runtime_live",
        refresh_seconds=settings.refresh_seconds,
        backend_ok=payload.backend_ok,
    )

    if payload.backend_error:
        st.error(f"Backend indisponible : {payload.backend_error}")

    render_kpi_cards(
        [
            KpiCard("Paquets captures", str(int(status.get("packets_captured", 0) or 0)), "capture active", "accent"),
            KpiCard("Flux actifs", str(int(status.get("active_flows", 0) or 0)), "fenetre courante", "success"),
            KpiCard("Flux finalises", str(int(status.get("finalized_flows", 0) or 0)), "prets pour analyse", "warning"),
            KpiCard("Erreurs parsing", str(int(status.get("packet_parse_errors", 0) or 0)), "pipeline live", "danger"),
        ]
    )

    left, right = st.columns([1.25, 0.95], gap="large")

    with left:
        with st.container(border=True):
            render_detail_list(
                "Etat session",
                "Informations runtime et compteurs live.",
                [
                    ("Session ID", status.get("session_id") or "-", "accent"),
                    ("Runtime", str(payload.summaries["runtime_label"]), "success" if payload.summaries["runtime_label"] == "RUNNING" else "warning"),
                    ("Interface", status.get("interface_name") or "-", "neutral"),
                    ("Capture filter", status.get("capture_filter") or "-", "neutral"),
                    ("Uptime", format_duration_seconds(status.get("uptime_seconds", 0)), "neutral"),
                    ("Predictions", str(int(status.get("predictions", 0) or 0)), "neutral"),
                    ("Alertes", str(int(status.get("alerts", 0) or 0)), "warning"),
                    ("Blocages", str(int(status.get("block_decisions", 0) or 0)), "danger"),
                ],
            )

    with right:
        with st.container(border=True):
            render_panel_title("Pipeline live", "Vue simplifiee du traitement en cours.")
            st.markdown(
                f"""
                1. Capture : `{'active' if status.get('running') else 'inactive'}`
                2. Aggregation flux : `{int(status.get('active_flows', 0) or 0)} flux actifs`
                3. Features : `construction live`
                4. Classification : `{int(status.get('predictions', 0) or 0)} predictions`
                5. Alertes : `{int(status.get('alerts', 0) or 0)}`
                6. Blocages : `{int(status.get('block_decisions', 0) or 0)}`
                """
            )

    with st.container(border=True):
        render_panel_title("Journal runtime", "Messages recents du moteur et du pipeline.")
        render_dataframe(payload.dataframes["logs"], height=320)

    if status.get("last_errors"):
        st.warning("Dernieres erreurs runtime : " + " | ".join(status["last_errors"][:5]))


render_runtime_live()
