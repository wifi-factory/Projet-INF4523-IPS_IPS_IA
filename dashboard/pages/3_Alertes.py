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
)


settings = get_dashboard_settings()


@st.fragment(run_every=fragment_interval(settings.refresh_seconds))
def render_alerts_live() -> None:
    payload = fetch_alerts_payload(settings)
    alerts_df = payload.dataframes["alerts"].copy()

    render_page_header(
        "Alertes",
        "Incidents detectes, niveaux de severite et actions associees.",
        pills=[backend_badge_html(payload.backend_ok)],
    )
    render_background_sync_status(
        scope_key="alertes",
        refresh_seconds=settings.refresh_seconds,
        backend_ok=payload.backend_ok,
    )

    if payload.backend_error:
        st.error(f"Backend indisponible : {payload.backend_error}")

    render_kpi_cards(
        [
            KpiCard("Critiques", str(payload.summaries["critical_count"]), "a traiter en priorite", "critical"),
            KpiCard("Elevees", str(payload.summaries["high_count"]), "surveillance renforcee", "warning"),
            KpiCard("Blocages", str(payload.summaries["blocking_count"]), "actions declenchees", "danger"),
            KpiCard("Sources uniques", str(payload.summaries["unique_sources"]), "IPs emettrices", "accent"),
        ]
    )

    severity_options = ["Toutes"] + sorted(alerts_df["Severite"].dropna().unique().tolist()) if not alerts_df.empty else ["Toutes"]
    ensure_option_state("alertes_severite_filtre", severity_options, "Toutes")
    selected_severity = st.selectbox("Severite", severity_options, key="alertes_severite_filtre")

    filtered_df = alerts_df
    if selected_severity != "Toutes":
        filtered_df = filtered_df[filtered_df["Severite"] == selected_severity]

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

        recent_alert = filtered_df.iloc[0].to_dict() if not filtered_df.empty else payload.summaries.get("recent_alert", {})
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


render_alerts_live()
