from __future__ import annotations

from dashboard.services.backend_client import BackendUnavailableError
from dashboard.services.live_provider import LiveProvider
from dashboard.config import build_dashboard_settings


class FakeClient:
    def get_live_interfaces(self):
        return {"interfaces": [{"index": "1", "label": "eth0"}]}

    def get_health(self):
        return {"status": "ok"}

    def get_live_status(self):
        return {
            "status": "running",
            "predictions": 100,
            "alerts": 25,
            "block_decisions": 5,
            "finalized_flows": 80,
            "active_flows": 4,
            "packet_parse_errors": 0,
        }

    def get_live_events(self, *, limit: int):
        return {
            "events": [
                {
                    "timestamp": "2026-04-03T16:42:16",
                    "prediction_label": "suspect",
                    "risk_score": 0.99,
                    "protocol": "tcp",
                    "src_ip": "172.30.1.21",
                    "dst_ip": "172.30.1.24",
                    "src_port": 44712,
                    "dst_port": 22,
                    "action_taken": "block_dry_run",
                    "status": "blocked",
                }
            ]
        }

    def get_live_alerts(self, *, limit: int):
        return {
            "alerts": [
                {
                    "timestamp": "2026-04-03T16:41:57",
                    "severity": "critical",
                    "attack_type": "Scan TCP",
                    "src_ip": "172.30.1.21",
                    "dst_ip": "172.30.1.24",
                    "action_taken": "block_dry_run",
                    "status": "open",
                    "risk_score": 0.99,
                }
            ]
        }

    def get_live_alerts_recent(self, *, since: str | None = None):
        return {
            "api_exposed_at": "2026-04-03T16:41:58",
            "total_available": 1,
            "new_alert_count": 0 if since else 1,
            "latest_alert": {
                "alert_id": "alt-001",
                "timestamp": "2026-04-03T16:41:57",
                "alert_created_at": "2026-04-03T16:41:57",
                "attack_type": "Scan TCP",
                "severity": "critical",
                "src_ip": "172.30.1.21",
                "dst_ip": "172.30.1.24",
                "action_taken": "block_dry_run",
                "status": "open",
                "risk_score": 0.99,
                "flow_finalized_at": "2026-04-03T16:41:56.500000",
                "prediction_done_at": "2026-04-03T16:41:56.700000",
                "latency_from_finalization_ms": 500.0,
            },
        }

    def get_live_blocking(self, *, limit: int):
        return {
            "blocking_events": [
                {
                    "timestamp": "2026-04-03T16:41:57",
                    "src_ip": "172.30.1.21",
                    "dst_ip": "172.30.1.24",
                    "protocol": "tcp",
                    "confidence": 0.99,
                    "triggered": True,
                    "status": "executed",
                    "reason": "blocked",
                }
            ]
        }

    def get_live_logs(self, *, limit: int):
        return {
            "logs": [
                {
                    "timestamp": "2026-04-03T16:42:18",
                    "level": "INFO",
                    "component": "live_runtime_service",
                    "message": "Capture active",
                    "category": "runtime",
                }
            ]
        }


def test_live_provider_builds_overview_summary() -> None:
    provider = LiveProvider(FakeClient(), build_dashboard_settings())
    payload = provider.get_overview_payload()

    assert payload.backend_ok is True
    assert payload.summaries["finalized_flows"] == "80"
    assert payload.summaries["suspect_rate"] == "25,0 %"
    assert not payload.dataframes["events"].empty


def test_live_provider_exposes_runtime_interfaces() -> None:
    provider = LiveProvider(FakeClient(), build_dashboard_settings())
    payload = provider.get_runtime_payload()

    assert payload.summaries["interfaces"][0]["label"] == "eth0"


def test_live_provider_builds_runtime_control_payload() -> None:
    provider = LiveProvider(FakeClient(), build_dashboard_settings())
    payload = provider.get_runtime_control_payload()

    assert payload.backend_ok is True
    assert payload.backend_error is None
    assert payload.interfaces_error is None
    assert payload.live_status["status"] == "running"
    assert payload.interfaces[0]["label"] == "eth0"


def test_live_provider_handles_backend_failure() -> None:
    class FailingClient(FakeClient):
        def get_health(self):
            raise BackendUnavailableError("backend down")

    provider = LiveProvider(FailingClient(), build_dashboard_settings())
    payload = provider.get_runtime_payload()

    assert payload.backend_ok is False


def test_live_provider_tolerates_partial_runtime_payload() -> None:
    class PartialClient(FakeClient):
        def get_live_status(self):
            return {"status": "running"}

        def get_live_interfaces(self):
            return {}

        def get_live_logs(self, *, limit: int):
            return {}

    provider = LiveProvider(PartialClient(), build_dashboard_settings())
    payload = provider.get_runtime_control_payload()

    assert payload.backend_ok is True
    assert payload.live_status["status"] == "running"
    assert payload.interfaces_error is None
    assert payload.interfaces == []


def test_live_provider_keeps_backend_ok_when_only_interfaces_fail() -> None:
    class InterfaceFailingClient(FakeClient):
        def get_live_interfaces(self):
            raise BackendUnavailableError("timed out")

    provider = LiveProvider(InterfaceFailingClient(), build_dashboard_settings())
    payload = provider.get_runtime_control_payload()

    assert payload.backend_ok is True
    assert payload.backend_error is None
    assert payload.interfaces_error == "timed out"
    assert payload.interfaces == []


def test_live_provider_exposes_recent_alert_payload() -> None:
    provider = LiveProvider(FakeClient(), build_dashboard_settings())
    payload = provider.get_recent_alert_payload()

    assert payload.backend_ok is True
    assert payload.api_exposed_at == "2026-04-03T16:41:58"
    assert payload.new_alert_count == 1
    assert payload.latest_alert is not None
    assert payload.latest_alert["alert_id"] == "alt-001"
