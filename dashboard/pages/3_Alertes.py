from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.badges import backend_badge_html
from dashboard.components.cartes import KpiCard, render_detail_list, render_kpi_cards, render_page_header, render_panel_title
from dashboard.config import get_dashboard_settings
from dashboard.components.tableaux import render_dataframe
from dashboard.services.live_provider import fetch_alerts_payload
from dashboard.utils.rafraichissement import (
    ensure_option_state,
    fragment_interval,
    render_background_sync_status,
    signature_changed,
)


settings = get_dashboard_settings()
_initial_payload = fetch_alerts_payload(settings)
_initial_alerts_df = _initial_payload.dataframes["alerts"].copy()
_severity_options = (
    ["Toutes"] + sorted(_initial_alerts_df["Severite"].dropna().unique().tolist())
    if not _initial_alerts_df.empty
    else ["Toutes"]
)
ensure_option_state("alertes_severite_filtre", _severity_options, "Toutes")
st.selectbox("Severite", _severity_options, key="alertes_severite_filtre")


@st.fragment(run_every=fragment_interval(settings.refresh_seconds))
def render_alerts_live() -> None:
    payload = fetch_alerts_payload(settings)
    alerts_df = payload.dataframes["alerts"].copy()
    selected_severity = str(st.session_state.get("alertes_severite_filtre", "Toutes"))

    header_signature = {"backend_ok": payload.backend_ok}
    if signature_changed("alerts_header_signature", header_signature):
        with ALERTS_HEADER_SLOT.container():
            render_page_header(
                "Alertes",
                "Incidents detectes, niveaux de severite et actions associees.",
                pills=[backend_badge_html(payload.backend_ok)],
            )

    with ALERTS_SYNC_SLOT.container():
        render_background_sync_status(
            scope_key="alertes",
            refresh_seconds=settings.refresh_seconds,
            backend_ok=payload.backend_ok,
        )

    error_signature = {"backend_error": payload.backend_error}
    if signature_changed("alerts_error_signature", error_signature):
        if payload.backend_error:
            with ALERTS_ERROR_SLOT.container():
                st.error(f"Backend indisponible : {payload.backend_error}")
        else:
            ALERTS_ERROR_SLOT.empty()

    kpi_signature = payload.summaries
    if signature_changed("alerts_kpi_signature", kpi_signature):
        with ALERTS_KPI_SLOT.container():
            render_kpi_cards(
                [
                    KpiCard("Critiques", str(payload.summaries["critical_count"]), "a traiter en priorite", "critical"),
                    KpiCard("Elevees", str(payload.summaries["high_count"]), "surveillance renforcee", "warning"),
                    KpiCard("Blocages", str(payload.summaries["blocking_count"]), "actions declenchees", "danger"),
                    KpiCard("Sources uniques", str(payload.summaries["unique_sources"]), "IPs emettrices", "accent"),
                ]
            )

    filtered_df = alerts_df
    if selected_severity != "Toutes":
        filtered_df = filtered_df[filtered_df["Severite"] == selected_severity]

    body_signature = {
        "selected_severity": selected_severity,
        "alerts": alerts_df,
        "filtered": filtered_df,
        "summaries": payload.summaries,
    }
    if signature_changed("alerts_body_signature", body_signature):
        with ALERTS_BODY_SLOT.container():
            left, right = st.columns([1.6, 0.85], gap="large")

            with left:
                with st.container(border=True):
                    render_panel_title("Liste des alertes", "Lecture detaillee des incidents les plus recents.")
                    render_dataframe(filtered_df, height=460)

            with right:
                with st.container(border=True):
                    render_panel_title("Resume severite", "Repartition visuelle des incidents.")
                    if alerts_df.empty:
                        st.info("Aucune alerte disponible.")
                    else:
                        counts = alerts_df["Severite"].value_counts()
                        for label in ["Critique", "Elevee", "Moyenne", "Faible", "Normale"]:
                            value = int(counts.get(label, 0))
                            st.progress(min(value / max(len(alerts_df), 1), 1.0), text=f"{label} : {value}")

                recent_alert = (
                    filtered_df.iloc[0].to_dict()
                    if not filtered_df.empty
                    else payload.summaries.get("recent_alert", {})
                )
                with st.container(border=True):
                    render_detail_list(
                        "Incident recent",
                        "Fiche detail rapide.",
                        [
                            ("Heure", str(recent_alert.get("Heure", "-")), "neutral"),
                            ("Severite", str(recent_alert.get("Severite", "-")), "warning"),
                            ("Type", str(recent_alert.get("Type", "-")), "neutral"),
                            ("Source", str(recent_alert.get("Source", "-")), "neutral"),
                            ("Destination", str(recent_alert.get("Destination", "-")), "neutral"),
                            ("Action", str(recent_alert.get("Action", "-")), "danger"),
                            ("Statut", str(recent_alert.get("Statut", "-")), "accent"),
                        ],
                    )


ALERTS_HEADER_SLOT = st.empty()
ALERTS_SYNC_SLOT = st.empty()
ALERTS_ERROR_SLOT = st.empty()
ALERTS_KPI_SLOT = st.empty()
ALERTS_BODY_SLOT = st.empty()
render_alerts_live()
