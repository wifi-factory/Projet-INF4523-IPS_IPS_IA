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
from dashboard.components.journal import render_timeline
from dashboard.services.live_provider import fetch_journal_payload
from dashboard.utils.rafraichissement import (
    ensure_option_state,
    fragment_interval,
    render_background_sync_status,
    signature_changed,
)


settings = get_dashboard_settings()
_initial_payload = fetch_journal_payload(settings)
_initial_journal_df = _initial_payload.dataframes["journal"].copy()
_level_options = (
    ["Tous"] + sorted(_initial_journal_df["Niveau"].dropna().unique().tolist())
    if not _initial_journal_df.empty
    else ["Tous"]
)
ensure_option_state("journal_niveau_filtre", _level_options, "Tous")
st.selectbox("Niveau", _level_options, key="journal_niveau_filtre")


@st.fragment(run_every=fragment_interval(settings.refresh_seconds))
def render_journal_live() -> None:
    payload = fetch_journal_payload(settings)
    journal_df = payload.dataframes["journal"].copy()
    selected_level = str(st.session_state.get("journal_niveau_filtre", "Tous"))

    header_signature = {"backend_ok": payload.backend_ok}
    if signature_changed("journal_header_signature", header_signature):
        with JOURNAL_HEADER_SLOT.container():
            render_page_header(
                "Journal trafic",
                "Fil chronologique du trafic et des evenements runtime.",
                pills=[backend_badge_html(payload.backend_ok)],
            )

    with JOURNAL_SYNC_SLOT.container():
        render_background_sync_status(
            scope_key="journal_trafic",
            refresh_seconds=settings.refresh_seconds,
            backend_ok=payload.backend_ok,
        )

    error_signature = {"backend_error": payload.backend_error}
    if signature_changed("journal_error_signature", error_signature):
        if payload.backend_error:
            with JOURNAL_ERROR_SLOT.container():
                st.error(f"Backend indisponible : {payload.backend_error}")
        else:
            JOURNAL_ERROR_SLOT.empty()

    kpi_signature = payload.summaries
    if signature_changed("journal_kpi_signature", kpi_signature):
        with JOURNAL_KPI_SLOT.container():
            render_kpi_cards(
                [
                    KpiCard("Lignes journal", str(payload.summaries["line_count"]), "session courante", "accent"),
                    KpiCard("Infos", str(payload.summaries["info_count"]), "etat et runtime", "success"),
                    KpiCard("Alertes", str(payload.summaries["alert_count"]), "detection live", "warning"),
                    KpiCard("Blocages", str(payload.summaries["blocking_count"]), "actions declenchees", "danger"),
                ]
            )

    filtered_df = journal_df
    if selected_level != "Tous":
        filtered_df = filtered_df[filtered_df["Niveau"] == selected_level]

    body_signature = {
        "selected_level": selected_level,
        "journal": journal_df,
        "filtered": filtered_df,
        "summaries": payload.summaries,
    }
    if signature_changed("journal_body_signature", body_signature):
        with JOURNAL_BODY_SLOT.container():
            left, right = st.columns([1.7, 0.8], gap="large")

            with left:
                with st.container(border=True):
                    render_panel_title("Flux chronologique", "Historique recent fusionnant runtime, alertes et decisions.")
                    render_timeline(filtered_df.head(20))

            with right:
                with st.container(border=True):
                    render_panel_title("Resume flux", "Volume recent par type de ligne.")
                    for label in ["INFO", "ALERTE", "SUSPECT", "BLOCAGE", "NORMAL"]:
                        count = int((journal_df["Niveau"] == label).sum()) if not journal_df.empty else 0
                        if count:
                            st.progress(min(count / max(len(journal_df), 1), 1.0), text=f"{label} : {count}")

                focus = (
                    filtered_df.iloc[0].to_dict()
                    if not filtered_df.empty
                    else payload.summaries.get("focus", {})
                )
                with st.container(border=True):
                    render_detail_list(
                        "Focus recent",
                        "Derniere sequence notable observee.",
                        [
                            ("Heure", str(focus.get("Heure", "-")), "neutral"),
                            ("Type", str(focus.get("Niveau", "-")), "warning"),
                            ("Categorie", str(focus.get("Type", "-")), "accent"),
                            ("Message", str(focus.get("Message", "-")), "neutral"),
                        ],
                    )


JOURNAL_HEADER_SLOT = st.empty()
JOURNAL_SYNC_SLOT = st.empty()
JOURNAL_ERROR_SLOT = st.empty()
JOURNAL_KPI_SLOT = st.empty()
JOURNAL_BODY_SLOT = st.empty()
render_journal_live()
