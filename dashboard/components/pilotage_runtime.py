from __future__ import annotations

from dataclasses import replace
from html import escape
import re

import streamlit as st

from dashboard.config import DashboardSettings, get_dashboard_settings
from dashboard.services.live_provider import (
    RuntimeControlPayload,
    fetch_runtime_control_payload,
    start_live_capture,
    stop_live_capture,
)
from dashboard.utils.rafraichissement import (
    ensure_option_state,
    fragment_interval,
    render_background_sync_status,
)


NO_INTERFACE_VALUE = "__aucune_interface__"
CACHED_INTERFACES_KEY = "sidebar_runtime_cached_interfaces"
SEED_PAYLOAD_KEY = "sidebar_runtime_seed_payload"


def _interface_label(interface: dict[str, object]) -> str:
    raw = (
        interface.get("label")
        or interface.get("name")
        or interface.get("index")
        or "-"
    )
    return str(raw)


def _normalize_interface_display(label: str) -> str:
    simplified = label.strip()
    replacements = {
        "Bluetooth Network Connection": "Bluetooth",
        "Adapter for loopback traffic capture": "Loopback",
        "Event Tracing for Windows (ETW) reader": "ETW",
    }
    if simplified in replacements:
        return replacements[simplified]
    if simplified.startswith("Local Area Connection* "):
        suffix = simplified.removeprefix("Local Area Connection* ").strip()
        return f"Ethernet {suffix}".strip()
    return simplified or label


def _friendly_interface_label(interface: dict[str, object]) -> str:
    raw = re.sub(r"^\s*\d+\.\s*", "", _interface_label(interface)).strip()
    if " (" in raw and raw.endswith(")"):
        candidate = raw.split(" (", 1)[1][:-1].strip()
        return _normalize_interface_display(candidate)
    return _normalize_interface_display(raw)


def _build_interface_choices(
    payload: RuntimeControlPayload,
) -> list[dict[str, str | None]]:
    if not payload.interfaces:
        return [
            {
                "display": "Aucune interface disponible",
                "value": None,
                "raw": NO_INTERFACE_VALUE,
            }
        ]

    seen_displays: dict[str, int] = {}
    choices: list[dict[str, str | None]] = []
    for interface in payload.interfaces:
        raw = _interface_label(interface)
        display = _friendly_interface_label(interface)
        value = str(interface.get("index") or raw)
        seen_displays[display] = seen_displays.get(display, 0) + 1
        if seen_displays[display] > 1 and interface.get("index"):
            display = f"{display} {interface['index']}"
        choices.append({"display": display, "value": value, "raw": raw})
    return choices


def _stabilize_payload(payload: RuntimeControlPayload) -> RuntimeControlPayload:
    cached_interfaces = st.session_state.get(CACHED_INTERFACES_KEY)
    if payload.interfaces:
        st.session_state[CACHED_INTERFACES_KEY] = list(payload.interfaces)
        return payload

    if payload.interfaces_error and cached_interfaces:
        return replace(payload, interfaces=list(cached_interfaces))

    return payload


def _sync_interface_state(payload: RuntimeControlPayload) -> str:
    choices = _build_interface_choices(payload)
    labels = [str(choice["display"]) for choice in choices]
    value_map = {
        str(choice["display"]): str(choice["value"])
        for choice in choices
        if choice["value"] is not None
    }
    st.session_state["sidebar_interface_value_map"] = value_map

    runtime_interface = str(payload.live_status.get("interface_name") or "").strip()
    default_label = labels[0]
    if runtime_interface:
        for choice in choices:
            possible_values = {
                str(choice["display"]),
                str(choice["raw"]),
                str(choice["value"]) if choice["value"] is not None else "",
            }
            if runtime_interface in possible_values:
                default_label = str(choice["display"])
                break
    return ensure_option_state("sidebar_interface_source", labels, default_label)


def _sync_toggle_state(payload: RuntimeControlPayload) -> bool:
    backend_running = bool(payload.live_status.get("running"))
    previous_backend = st.session_state.get("sidebar_runtime_backend_running")
    toggle_key = "sidebar_runtime_toggle"

    if toggle_key not in st.session_state:
        st.session_state[toggle_key] = backend_running
    elif previous_backend is None or st.session_state[toggle_key] == previous_backend:
        st.session_state[toggle_key] = backend_running

    st.session_state["sidebar_runtime_backend_running"] = backend_running
    return bool(st.session_state[toggle_key])


def _set_feedback(level: str, message: str) -> None:
    st.session_state["sidebar_runtime_feedback"] = (level, message)


def _handle_runtime_toggle(settings: DashboardSettings) -> None:
    desired_running = bool(st.session_state.get("sidebar_runtime_toggle"))
    previous_running = bool(
        st.session_state.get("sidebar_runtime_backend_running", False)
    )
    selected_interface = str(st.session_state.get("sidebar_interface_source", "")).strip()
    interface_value_map = st.session_state.get("sidebar_interface_value_map", {})
    selected_interface_value = str(
        interface_value_map.get(selected_interface, "")
    ).strip()

    try:
        if desired_running:
            if not selected_interface_value:
                raise RuntimeError(
                    "Aucune interface reseau disponible pour demarrer la capture."
                )
            start_live_capture(
                interface_name=selected_interface_value,
                capture_filter=None,
                settings=settings,
            )
            _set_feedback("success", f"Runtime demarre sur {selected_interface}.")
        else:
            stop_live_capture(settings)
            _set_feedback("success", "Runtime arrete.")
    except Exception as exc:
        st.session_state["sidebar_runtime_toggle"] = previous_running
        _set_feedback("error", f"Echec du pilotage runtime : {exc}")


def _render_status_card(payload: RuntimeControlPayload, selected_interface: str) -> None:
    runtime_label = "ON" if bool(payload.live_status.get("running")) else "OFF"
    session_id = str(payload.live_status.get("session_id") or "-")
    current_interface = str(payload.live_status.get("interface_name") or "").strip()
    display_interface = (
        selected_interface
        if selected_interface and selected_interface != "Aucune interface disponible"
        else "-"
    )
    if current_interface:
        for choice in _build_interface_choices(payload):
            possible_values = {
                str(choice["display"]),
                str(choice["raw"]),
                str(choice["value"]) if choice["value"] is not None else "",
            }
            if current_interface in possible_values:
                display_interface = str(choice["display"])
                break
        else:
            display_interface = current_interface
    st.markdown(
        f"""
        <div class="sidebar-runtime-card">
          <div class="sidebar-runtime-card__title">Pilotage runtime</div>
          <div class="sidebar-runtime-card__subtitle">Capture live et etat du moteur</div>
          <div class="sidebar-runtime-summary">
            <div class="sidebar-runtime-summary__row">
              <span>Backend status</span>
              <strong class="sidebar-runtime-summary__value">{escape(payload.backend_status)}</strong>
            </div>
            <div class="sidebar-runtime-summary__row">
              <span>Runtime</span>
              <strong class="sidebar-runtime-summary__value">{escape(runtime_label)}</strong>
            </div>
            <div class="sidebar-runtime-summary__row">
              <span>Interface</span>
              <strong class="sidebar-runtime-summary__value">{escape(display_interface)}</strong>
            </div>
            <div class="sidebar-runtime-summary__row">
              <span>Session</span>
              <strong class="sidebar-runtime-summary__value">{escape(session_id)}</strong>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_runtime_status_panel(
    payload: RuntimeControlPayload,
    selected_interface: str,
    refresh_seconds: int,
) -> None:
    _render_status_card(payload, selected_interface)
    render_background_sync_status(
        scope_key="sidebar_runtime",
        refresh_seconds=refresh_seconds,
        backend_ok=payload.backend_ok,
    )

    if payload.backend_error:
        st.error(f"Backend indisponible : {payload.backend_error}")
    elif payload.interfaces_error:
        st.caption(
            "Rafraichissement des interfaces indisponible : "
            f"{payload.interfaces_error}"
        )

    feedback = st.session_state.get("sidebar_runtime_feedback")
    if feedback:
        level, message = feedback
        if level == "success":
            st.success(message)
        else:
            st.error(message)


def render_runtime_sidebar_panel(settings: DashboardSettings | None = None) -> None:
    resolved_settings = settings or get_dashboard_settings()
    initial_payload = _stabilize_payload(fetch_runtime_control_payload(resolved_settings))
    st.session_state[SEED_PAYLOAD_KEY] = initial_payload

    choices = _build_interface_choices(initial_payload)
    labels = [str(choice["display"]) for choice in choices]
    _sync_interface_state(initial_payload)
    _sync_toggle_state(initial_payload)

    @st.fragment(run_every=fragment_interval(resolved_settings.refresh_seconds))
    def render_runtime_sidebar_live() -> None:
        seeded_payload = st.session_state.pop(SEED_PAYLOAD_KEY, None)
        payload = seeded_payload or fetch_runtime_control_payload(resolved_settings)
        payload = _stabilize_payload(payload)
        _sync_toggle_state(payload)
        selected_interface = str(
            st.session_state.get("sidebar_interface_source", labels[0])
        )
        _render_runtime_status_panel(
            payload=payload,
            selected_interface=selected_interface,
            refresh_seconds=resolved_settings.refresh_seconds,
        )

    render_runtime_sidebar_live()

    backend_running = bool(initial_payload.live_status.get("running"))
    no_interfaces = len(choices) == 1 and choices[0]["value"] is None

    st.selectbox(
        "Interface source",
        labels,
        key="sidebar_interface_source",
        disabled=not initial_payload.backend_ok or no_interfaces or backend_running,
    )
    st.toggle(
        "Runtime actif",
        key="sidebar_runtime_toggle",
        on_change=_handle_runtime_toggle,
        args=(resolved_settings,),
        disabled=not initial_payload.backend_ok or (no_interfaces and not backend_running),
        help="Active ou arrete la capture et le traitement live.",
    )

    if no_interfaces and initial_payload.backend_ok and not backend_running:
        st.caption("Aucune interface reseau detectee pour demarrer le runtime.")
