from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.pilotage_runtime import render_runtime_sidebar_panel
from dashboard.config import get_dashboard_settings


st.set_page_config(page_title="Pilotage runtime test", layout="wide")

with st.sidebar:
    render_runtime_sidebar_panel(get_dashboard_settings())

st.write("test")
