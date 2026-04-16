from __future__ import annotations

import httpx

from dashboard.services.backend_client import BackendClient, BackendUnavailableError


def test_backend_client_reads_live_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/live/status":
            return httpx.Response(200, json={"status": "running", "running": True})
        return httpx.Response(200, json={"status": "ok"})

    client = BackendClient(
        "http://backend.local",
        transport=httpx.MockTransport(handler),
    )
    try:
        payload = client.get_live_status()
    finally:
        client.close()

    assert payload["status"] == "running"
    assert payload["running"] is True


def test_backend_client_reads_interfaces_and_controls_runtime() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/live/interfaces":
            return httpx.Response(
                200,
                json={"interfaces": [{"index": "1", "label": "eth0"}]},
            )
        if request.url.path == "/live/start":
            return httpx.Response(200, json={"status": "running", "running": True, "interface_name": "eth0"})
        if request.url.path == "/live/stop":
            return httpx.Response(200, json={"status": "stopped", "running": False})
        return httpx.Response(200, json={"status": "ok"})

    client = BackendClient(
        "http://backend.local",
        transport=httpx.MockTransport(handler),
    )
    try:
        interfaces = client.get_live_interfaces()
        started = client.start_live_monitoring(interface_name="eth0", capture_filter="ip")
        stopped = client.stop_live_monitoring()
    finally:
        client.close()

    assert interfaces["interfaces"][0]["label"] == "eth0"
    assert started["status"] == "running"
    assert stopped["status"] == "stopped"


def test_backend_client_raises_when_backend_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "unavailable"})

    client = BackendClient(
        "http://backend.local",
        transport=httpx.MockTransport(handler),
    )
    try:
        try:
            client.get_health()
        except BackendUnavailableError as exc:
            assert "503" in str(exc)
        else:
            raise AssertionError("BackendUnavailableError attendu")
    finally:
        client.close()
