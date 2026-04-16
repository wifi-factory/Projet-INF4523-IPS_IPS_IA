from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent
TEST_APP = ROOT / "apps" / "sidebar_runtime_test_app.py"


def test_runtime_sidebar_simplifies_interface_labels() -> None:
    import dashboard.components.pilotage_runtime as runtime_panel

    assert runtime_panel._friendly_interface_label(
        {"index": "5", "label": r"5. \Device\NPF_{ABC} (Wi-Fi)"}
    ) == "Wi-Fi"
    assert runtime_panel._friendly_interface_label(
        {"index": "8", "label": r"8. \Device\NPF_{DEF} (Ethernet 3)"}
    ) == "Ethernet 3"
    assert runtime_panel._friendly_interface_label(
        {"index": "1", "label": r"1. \Device\NPF_{XYZ} (Local Area Connection* 9)"}
    ) == "Ethernet 9"


def test_runtime_sidebar_renders_controls(monkeypatch, runtime_control_payload) -> None:
    import dashboard.components.pilotage_runtime as runtime_panel

    monkeypatch.setattr(runtime_panel, "fetch_runtime_control_payload", lambda *args, **kwargs: runtime_control_payload)

    app = AppTest.from_file(str(TEST_APP))
    app.run()

    assert not app.exception
    assert app.selectbox[0].label == "Interface source"
    assert app.toggle[0].label == "Runtime actif"


def test_runtime_sidebar_disables_controls_when_backend_down(monkeypatch, runtime_control_payload) -> None:
    import dashboard.components.pilotage_runtime as runtime_panel

    degraded_payload = replace(
        runtime_control_payload,
        backend_ok=False,
        backend_status="NOK",
        backend_error="backend down",
    )
    monkeypatch.setattr(runtime_panel, "fetch_runtime_control_payload", lambda *args, **kwargs: degraded_payload)

    app = AppTest.from_file(str(TEST_APP))
    app.run()

    assert not app.exception
    assert app.selectbox[0].proto.disabled is True
    assert app.toggle[0].proto.disabled is True


def test_runtime_sidebar_handles_no_interface_available(monkeypatch, runtime_control_payload) -> None:
    import dashboard.components.pilotage_runtime as runtime_panel

    payload = replace(
        runtime_control_payload,
        live_status={**runtime_control_payload.live_status, "running": False, "status": "stopped", "interface_name": None},
        interfaces=[],
    )
    monkeypatch.setattr(runtime_panel, "fetch_runtime_control_payload", lambda *args, **kwargs: payload)

    app = AppTest.from_file(str(TEST_APP))
    app.run()

    assert not app.exception
    assert app.selectbox[0].options == ["Aucune interface disponible"]
    assert app.toggle[0].proto.disabled is True


def test_runtime_sidebar_displays_simplified_interface_names(monkeypatch, runtime_control_payload) -> None:
    import dashboard.components.pilotage_runtime as runtime_panel

    payload = replace(
        runtime_control_payload,
        interfaces=[
            {"index": "5", "label": r"5. \Device\NPF_{ABC} (Wi-Fi)"},
            {"index": "8", "label": r"8. \Device\NPF_{DEF} (Ethernet 3)"},
            {"index": "11", "label": r"11. \Device\NPF_{XYZ} (Ethernet)"},
        ],
    )
    monkeypatch.setattr(runtime_panel, "fetch_runtime_control_payload", lambda *args, **kwargs: payload)

    app = AppTest.from_file(str(TEST_APP))
    app.run()

    assert not app.exception
    assert app.selectbox[0].options == ["Wi-Fi", "Ethernet 3", "Ethernet"]


def test_runtime_sidebar_starts_runtime(monkeypatch, runtime_control_payload) -> None:
    import dashboard.components.pilotage_runtime as runtime_panel

    calls: list[tuple[str, str | None]] = []
    payload = replace(
        runtime_control_payload,
        live_status={**runtime_control_payload.live_status, "running": False, "status": "stopped", "interface_name": None},
    )
    monkeypatch.setattr(runtime_panel, "fetch_runtime_control_payload", lambda *args, **kwargs: payload)
    monkeypatch.setattr(
        runtime_panel,
        "start_live_capture",
        lambda *, interface_name, capture_filter, settings=None: calls.append((str(interface_name), capture_filter)),
    )
    monkeypatch.setattr(runtime_panel, "stop_live_capture", lambda settings=None: None)

    app = AppTest.from_file(str(TEST_APP))
    app.run()
    app.selectbox[0].select("eth1").run()
    app.toggle[0].set_value(True).run()

    assert calls == [("2", None)]


def test_runtime_sidebar_stops_runtime(monkeypatch, runtime_control_payload) -> None:
    import dashboard.components.pilotage_runtime as runtime_panel

    stop_calls: list[str] = []
    monkeypatch.setattr(runtime_panel, "fetch_runtime_control_payload", lambda *args, **kwargs: runtime_control_payload)
    monkeypatch.setattr(runtime_panel, "start_live_capture", lambda *, interface_name, capture_filter, settings=None: None)
    monkeypatch.setattr(runtime_panel, "stop_live_capture", lambda settings=None: stop_calls.append("stopped"))

    app = AppTest.from_file(str(TEST_APP))
    app.run()
    app.toggle[0].set_value(False).run()

    assert stop_calls == ["stopped"]


def test_runtime_sidebar_reuses_cached_interfaces_when_refresh_fails(
    monkeypatch,
    runtime_control_payload,
) -> None:
    import dashboard.components.pilotage_runtime as runtime_panel

    payloads = iter(
        [
            runtime_control_payload,
            replace(
                runtime_control_payload,
                interfaces=[],
                interfaces_error="timed out",
            ),
        ]
    )
    monkeypatch.setattr(
        runtime_panel,
        "fetch_runtime_control_payload",
        lambda *args, **kwargs: next(payloads),
    )

    app = AppTest.from_file(str(TEST_APP))
    app.run()
    assert app.selectbox[0].options == ["eth0", "eth1"]

    app.run()

    assert not app.exception
    assert app.selectbox[0].options == ["eth0", "eth1"]
