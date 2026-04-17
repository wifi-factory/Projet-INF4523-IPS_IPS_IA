from __future__ import annotations

import hashlib
import json
from datetime import datetime
from html import escape
from typing import Any, Mapping, Sequence

import pandas as pd

import streamlit as st


def fragment_interval(refresh_seconds: int) -> str:
    return f"{int(refresh_seconds)}s"


def _normalize_signature_source(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        frame = value.copy()
        frame = frame.where(pd.notna(frame), None)
        return {
            "__type__": "dataframe",
            "columns": list(frame.columns),
            "rows": frame.to_dict(orient="records"),
        }
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_signature_source(resolved)
            for key, resolved in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_signature_source(item) for item in value]
    if isinstance(value, set):
        return sorted(_normalize_signature_source(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_signature(value: Any) -> str:
    normalized = _normalize_signature_source(value)
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def signature_changed(key: str, value: Any) -> bool:
    signature = build_signature(value)
    previous = st.session_state.get(key)
    if previous == signature:
        return False
    st.session_state[key] = signature
    return True


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
