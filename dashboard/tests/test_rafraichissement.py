from __future__ import annotations

from dashboard.utils.rafraichissement import build_sync_status_label, fragment_interval


def test_fragment_interval_formats_seconds() -> None:
    assert fragment_interval(3) == "3s"


def test_build_sync_status_label_reflects_backend_state() -> None:
    ok_label = build_sync_status_label(
        refresh_seconds=4,
        last_sync="12:34:56",
        backend_ok=True,
    )
    degraded_label = build_sync_status_label(
        refresh_seconds=4,
        last_sync="12:34:56",
        backend_ok=False,
    )

    assert "Synchronisation silencieuse toutes les 4 s" in ok_label
    assert "Derniere synchro 12:34:56" in ok_label
    assert "attente backend" not in ok_label
    assert "attente backend" in degraded_label
