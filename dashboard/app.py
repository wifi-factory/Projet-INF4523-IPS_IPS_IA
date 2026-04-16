from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.cartes import load_dashboard_css, render_sidebar_brand
from dashboard.components.alerte_live import render_recent_alert_sidebar_panel
from dashboard.components.pilotage_runtime import render_runtime_sidebar_panel
from dashboard.config import get_dashboard_settings
from dashboard.utils.rafraichissement import fragment_interval


settings = get_dashboard_settings()

st.set_page_config(
    page_title="IPS IA - Console live",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dashboard_css()

pages_dir = Path(__file__).resolve().parent / "pages"
navigation = st.navigation(
    [
        st.Page(str(pages_dir / "1_Vue_ensemble.py"), title="Vue ensemble", icon="🏠"),
        st.Page(str(pages_dir / "2_Runtime_live.py"), title="Runtime live", icon="📡"),
        st.Page(str(pages_dir / "3_Alertes.py"), title="Alertes", icon="🚨"),
        st.Page(str(pages_dir / "4_Evenements.py"), title="Evenements", icon="📋"),
        st.Page(str(pages_dir / "5_Journal_trafic.py"), title="Journal trafic", icon="🕒"),
    ],
    position="sidebar",
)

with st.sidebar:
    render_sidebar_brand(settings)

    @st.fragment(run_every=fragment_interval(settings.refresh_seconds))
    def render_sidebar_runtime_panel() -> None:
        render_runtime_sidebar_panel(settings)

    render_sidebar_runtime_panel()

    @st.fragment(run_every=fragment_interval(settings.alert_pulse_refresh_seconds))
    def render_sidebar_recent_alert() -> None:
        render_recent_alert_sidebar_panel(settings)

    render_sidebar_recent_alert()

navigation.run()
