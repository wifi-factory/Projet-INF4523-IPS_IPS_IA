from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]


def _fake_payload(sample_payload):
    return lambda *args, **kwargs: sample_payload


def test_app_boots(monkeypatch, sample_payload, runtime_control_payload) -> None:
    from types import SimpleNamespace

    import streamlit as st
    import dashboard.services.live_provider as provider
    import dashboard.components.alerte_live as alert_panel
    import dashboard.components.pilotage_runtime as runtime_panel

    class DummyNavigation:
        def run(self) -> None:
            return None

    monkeypatch.setenv("IPS_DASHBOARD_REFRESH_SECONDS", "60")
    monkeypatch.setenv("IPS_DASHBOARD_ALERT_PULSE_REFRESH_SECONDS", "60")
    monkeypatch.setattr(st, "fragment", lambda *args, **kwargs: (lambda fn: fn))
    monkeypatch.setattr(st, "navigation", lambda *args, **kwargs: DummyNavigation())
    monkeypatch.setattr(provider, "fetch_overview_payload", _fake_payload(sample_payload))
    monkeypatch.setattr(runtime_panel, "fetch_runtime_control_payload", _fake_payload(runtime_control_payload))
    monkeypatch.setattr(
        alert_panel,
        "fetch_recent_alert_payload",
        lambda *args, **kwargs: SimpleNamespace(
            backend_ok=True,
            backend_error=None,
            api_exposed_at="2026-04-03T16:41:58",
            total_available=0,
            new_alert_count=0,
            latest_alert=None,
        ),
    )

    app = AppTest.from_file(str(ROOT / "dashboard" / "app.py"))
    app.run(timeout=10)

    assert not app.exception
    assert app.selectbox
    assert app.toggle


def test_overview_page_renders(monkeypatch, sample_payload) -> None:
    import dashboard.services.live_provider as provider

    monkeypatch.setattr(provider, "fetch_overview_payload", _fake_payload(sample_payload))
    app = AppTest.from_file(str(ROOT / "dashboard" / "pages" / "1_Vue_ensemble.py"))
    app.run()

    assert not app.exception
    assert "Vue ensemble" in "".join(markdown.value for markdown in app.markdown)


def test_alerts_page_shows_backend_error(monkeypatch, sample_payload) -> None:
    import dashboard.services.live_provider as provider

    error_payload = sample_payload
    error_payload = type(sample_payload)(
        backend_ok=False,
        backend_status="NOK",
        backend_error="backend down",
        live_status=sample_payload.live_status,
        dataframes=sample_payload.dataframes,
        summaries=sample_payload.summaries,
    )

    monkeypatch.setattr(provider, "fetch_alerts_payload", _fake_payload(error_payload))
    app = AppTest.from_file(str(ROOT / "dashboard" / "pages" / "3_Alertes.py"))
    app.run()

    assert not app.exception
    assert app.error


def test_runtime_page_renders_summary(monkeypatch, sample_payload) -> None:
    import dashboard.services.live_provider as provider

    monkeypatch.setattr(provider, "fetch_runtime_payload", _fake_payload(sample_payload))
    app = AppTest.from_file(str(ROOT / "dashboard" / "pages" / "2_Runtime_live.py"))
    app.run()

    assert not app.exception
    assert "Runtime live" in "".join(markdown.value for markdown in app.markdown)
    assert app.dataframe


def test_events_page_renders(monkeypatch, sample_payload) -> None:
    import dashboard.services.live_provider as provider

    monkeypatch.setattr(provider, "fetch_events_payload", _fake_payload(sample_payload))
    app = AppTest.from_file(str(ROOT / "dashboard" / "pages" / "4_Evenements.py"))
    app.run()

    assert not app.exception
    assert "Evenements" in "".join(markdown.value for markdown in app.markdown)
    assert app.dataframe


def test_journal_page_renders(monkeypatch, sample_payload) -> None:
    import dashboard.services.live_provider as provider

    monkeypatch.setattr(provider, "fetch_journal_payload", _fake_payload(sample_payload))
    app = AppTest.from_file(str(ROOT / "dashboard" / "pages" / "5_Journal_trafic.py"))
    app.run()

    assert not app.exception
    assert "Journal trafic" in "".join(markdown.value for markdown in app.markdown)
    assert app.selectbox
