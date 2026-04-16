from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Sequence

import streamlit as st


def fragment_interval(refresh_seconds: int) -> str:
    return f"{int(refresh_seconds)}s"


def ensure_option_state(key: str, options: Sequence[str], default: str | None = None) -> str:
    normalized = list(options)
    if not normalized:
        raise ValueError("options ne peut pas etre vide")
    fallback = default if default in normalized else normalized[0]
    if key not in st.session_state or st.session_state[key] not in normalized:
        st.session_state[key] = fallback
    return str(st.session_state[key])


def build_sync_status_label(
    *,
    refresh_seconds: int,
    last_sync: str,
    backend_ok: bool,
) -> str:
    status = (
        f"Synchronisation silencieuse toutes les {int(refresh_seconds)} s · "
        f"Derniere synchro {last_sync}"
    )
    if not backend_ok:
        status += " · attente backend"
    return status


def render_background_sync_status(
    *,
    scope_key: str,
    refresh_seconds: int,
    backend_ok: bool,
) -> None:
    sync_key = f"{scope_key}__last_successful_sync"
    if backend_ok:
        st.session_state[sync_key] = datetime.now().strftime("%H:%M:%S")

    last_sync = st.session_state.get(sync_key, "--:--:--")
    status = build_sync_status_label(
        refresh_seconds=refresh_seconds,
        last_sync=last_sync,
        backend_ok=backend_ok,
    )

    tone = "ok" if backend_ok else "warning"
    st.markdown(
        f"<div class='sync-status sync-status--{escape(tone)}'>{escape(status)}</div>",
        unsafe_allow_html=True,
    )
