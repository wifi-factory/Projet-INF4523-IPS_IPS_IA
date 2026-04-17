from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.badges import backend_badge_html
from dashboard.components.cartes import KpiCard, render_detail_list, render_kpi_cards, render_page_header, render_panel_title
from dashboard.config import get_dashboard_settings
from dashboard.components.tableaux import render_dataframe
from dashboard.services.live_provider import fetch_events_payload
from dashboard.utils.rafraichissement import (
    ensure_option_state,
    fragment_interval,
    render_background_sync_status,
    signature_changed,
)


settings = get_dashboard_settings()
_initial_payload = fetch_events_payload(settings)
_initial_events_df = _initial_payload.dataframes["events"].copy()
_label_options = (
    ["Tous"] + sorted(_initial_events_df["Label"].dropna().unique().tolist())
    if not _initial_events_df.empty
    else ["Tous"]
)
_proto_options = (
    ["Tous"] + sorted(_initial_events_df["Proto"].dropna().unique().tolist())
    if not _initial_events_df.empty
    else ["Tous"]
)
ensure_option_state("evenements_label_filtre", _label_options, "Tous")
ensure_option_state("evenements_proto_filtre", _proto_options, "Tous")
if "evenements_score_minimum" not in st.session_state:
    st.session_state["evenements_score_minimum"] = 0.0

filter_cols = st.columns(3)
filter_cols[0].selectbox("Label", _label_options, key="evenements_label_filtre")
filter_cols[1].selectbox("Protocole", _proto_options, key="evenements_proto_filtre")
filter_cols[2].slider(
    "Score minimum",
    min_value=0.0,
    max_value=1.0,
    step=0.05,
    key="evenements_score_minimum",
)


@st.fragment(run_every=fragment_interval(settings.refresh_seconds))
def render_events_live() -> None:
    payload = fetch_events_payload(settings)
    events_df = payload.dataframes["events"].copy()
    selected_label = str(st.session_state.get("evenements_label_filtre", "Tous"))
    selected_proto = str(st.session_state.get("evenements_proto_filtre", "Tous"))
    minimum_score = float(st.session_state.get("evenements_score_minimum", 0.0))

    header_signature = {"backend_ok": payload.backend_ok}
    if signature_changed("events_header_signature", header_signature):
        with EVENTS_HEADER_SLOT.container():
            render_page_header(
                "Evenements",
                "Flux classes, scores, protocoles et actions associees.",
                pills=[backend_badge_html(payload.backend_ok)],
            )

    with EVENTS_SYNC_SLOT.container():
        render_background_sync_status(
            scope_key="evenements",
            refresh_seconds=settings.refresh_seconds,
            backend_ok=payload.backend_ok,
        )

    error_signature = {"backend_error": payload.backend_error}
    if signature_changed("events_error_signature", error_signature):
        if payload.backend_error:
            with EVENTS_ERROR_SLOT.container():
                st.error(f"Backend indisponible : {payload.backend_error}")
        else:
            EVENTS_ERROR_SLOT.empty()

    kpi_signature = payload.summaries
    if signature_changed("events_kpi_signature", kpi_signature):
        with EVENTS_KPI_SLOT.container():
            render_kpi_cards(
                [
                    KpiCard("Evenements normaux", str(payload.summaries["normal_count"]), "trafic autorise", "success"),
                    KpiCard("Evenements suspects", str(payload.summaries["suspect_count"]), "a surveiller", "warning"),
                    KpiCard("Score moyen suspect", str(payload.summaries["mean_suspect_score"]), "flux suspects", "accent"),
                    KpiCard("Protocoles actifs", str(payload.summaries["protocol_count"]), "TCP / UDP / ICMP", "danger"),
                ]
            )

    filtered_df = events_df
    if selected_label != "Tous":
        filtered_df = filtered_df[filtered_df["Label"] == selected_label]
    if selected_proto != "Tous":
        filtered_df = filtered_df[filtered_df["Proto"] == selected_proto]
    if not filtered_df.empty:
        numeric_scores = pd.to_numeric(filtered_df["Score"], errors="coerce").fillna(0.0)
        filtered_df = filtered_df[numeric_scores >= minimum_score]

    body_signature = {
        "selected_label": selected_label,
        "selected_proto": selected_proto,
        "minimum_score": minimum_score,
        "events": events_df,
        "filtered": filtered_df,
        "summaries": payload.summaries,
    }
    if signature_changed("events_body_signature", body_signature):
        with EVENTS_BODY_SLOT.container():
            left, right = st.columns([1.7, 0.8], gap="large")

            with left:
                with st.container(border=True):
                    render_panel_title("Table des evenements", "Lecture detaillee des flux recents classes par le moteur.")
                    render_dataframe(filtered_df, height=470)

            selected_event = (
                filtered_df.iloc[0].to_dict()
                if not filtered_df.empty
                else payload.summaries.get("selected_event", {})
            )
            with right:
                with st.container(border=True):
                    render_panel_title("Resume trafic", "Vision rapide des classes et protocoles.")
                    total_events = max(len(events_df), 1)
                    st.progress(
                        min(payload.summaries["normal_count"] / total_events, 1.0),
                        text=f"Normal : {payload.summaries['normal_count']}",
                    )
                    st.progress(
                        min(payload.summaries["suspect_count"] / total_events, 1.0),
                        text=f"Suspect : {payload.summaries['suspect_count']}",
                    )
                    if not events_df.empty:
                        st.caption("Protocoles actifs : " + " / ".join(sorted(events_df["Proto"].dropna().unique().tolist())))

                with st.container(border=True):
                    render_detail_list(
                        "Evenement selectionne",
                        "Fiche de lecture rapide du flux courant.",
                        [
                            ("Heure", str(selected_event.get("Heure", "-")), "neutral"),
                            ("Label", str(selected_event.get("Label", "-")), "warning"),
                            ("Score", str(selected_event.get("Score", "-")), "accent"),
                            ("Source", str(selected_event.get("Source", "-")), "neutral"),
                            ("Destination", str(selected_event.get("Destination", "-")), "neutral"),
                            ("Port dst", str(selected_event.get("Port dst", "-")), "neutral"),
                            ("Protocole", str(selected_event.get("Proto", "-")), "neutral"),
                            ("Action", str(selected_event.get("Action", "-")), "danger"),
                        ],
                    )


EVENTS_HEADER_SLOT = st.empty()
EVENTS_SYNC_SLOT = st.empty()
EVENTS_ERROR_SLOT = st.empty()
EVENTS_KPI_SLOT = st.empty()
EVENTS_BODY_SLOT = st.empty()
render_events_live()
