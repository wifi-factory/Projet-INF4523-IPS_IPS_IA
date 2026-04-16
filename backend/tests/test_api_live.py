from __future__ import annotations


def build_api_test_packets(now_ts, packet_factory):
    return [
        packet_factory(
            timestamp=now_ts,
            src_ip="10.10.0.1",
            dst_ip="10.10.0.2",
            protocol="TCP",
            src_port=51000,
            dst_port=80,
            packet_length=60,
            syn=1,
        ),
        packet_factory(
            timestamp=now_ts + 0.01,
            src_ip="10.10.0.2",
            dst_ip="10.10.0.1",
            protocol="TCP",
            src_port=80,
            dst_port=51000,
            packet_length=60,
            syn=1,
            ack=1,
        ),
        packet_factory(
            timestamp=now_ts + 0.02,
            src_ip="10.10.0.1",
            dst_ip="10.10.0.2",
            protocol="TCP",
            src_port=51000,
            dst_port=80,
            packet_length=300,
            ack=1,
            psh=1,
        ),
        packet_factory(
            timestamp=now_ts + 0.03,
            src_ip="10.10.0.1",
            dst_ip="10.10.0.2",
            protocol="TCP",
            src_port=51000,
            dst_port=80,
            packet_length=60,
            ack=1,
            fin=1,
        ),
    ]


def build_api_suspect_packets(now_ts, packet_factory):
    return [
        packet_factory(
            timestamp=now_ts + (offset * 0.01),
            src_ip="172.16.2.10",
            dst_ip="172.16.2.20",
            protocol="TCP",
            src_port=45000 + offset,
            dst_port=4400 + offset,
            packet_length=1500,
            syn=1,
            rst=1,
        )
        for offset in range(40)
    ]


def test_live_api_lists_capture_interfaces(client_with_live):
    client, _, _ = client_with_live

    response = client.get("/live/interfaces")

    assert response.status_code == 200
    payload = response.json()
    assert payload["interfaces"]
    assert payload["interfaces"][0]["index"] == "1"
    assert "test0" in payload["interfaces"][0]["label"]


def test_live_api_start_status_stop(
    client_with_live,
    packet_factory,
    now_ts,
    replay_waiter,
):
    client, _, manual_capture_service = client_with_live

    start_response = client.post(
        "/live/start",
        json={"interface_name": "test0", "flush_interval_seconds": 0.05},
    )

    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"
    assert start_response.json()["alert_confidence_threshold"] == 0.95
    assert start_response.json()["block_confidence_threshold"] == 0.99

    manual_capture_service.emit_packets(build_api_test_packets(now_ts, packet_factory))
    replay_waiter(lambda: client.get("/live/status").json()["predictions"] >= 1)

    status_response = client.get("/live/status")
    assert status_response.status_code == 200
    assert status_response.json()["running"] is True
    assert status_response.json()["alert_confidence_threshold"] == 0.95
    assert status_response.json()["block_confidence_threshold"] == 0.99

    stop_response = client.post("/live/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"
    assert stop_response.json()["predictions"] >= 1


def test_live_api_returns_validation_error_for_bad_payload(client):
    response = client.post(
        "/live/start",
        json={"interface_name": "   ", "flush_interval_seconds": 0},
    )

    assert response.status_code == 422


def test_live_api_rejects_second_start_with_conflict(client_with_live):
    client, _, _ = client_with_live

    first = client.post(
        "/live/start",
        json={"interface_name": "test0", "flush_interval_seconds": 0.05},
    )
    second = client.post(
        "/live/start",
        json={"interface_name": "test0", "flush_interval_seconds": 0.05},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error_type"] == "LiveRuntimeError"


def test_live_api_stop_without_active_session_returns_stopped_status(client_with_live):
    client, _, _ = client_with_live

    response = client.post("/live/stop")

    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    assert response.json()["running"] is False


def test_live_api_exposes_history_endpoints(
    client_with_live,
    packet_factory,
    now_ts,
    replay_waiter,
):
    client, _, manual_capture_service = client_with_live

    start_response = client.post(
        "/live/start",
        json={"interface_name": "test0", "flush_interval_seconds": 0.05},
    )
    assert start_response.status_code == 200

    manual_capture_service.emit_packets(build_api_test_packets(now_ts, packet_factory))
    replay_waiter(lambda: client.get("/live/status").json()["predictions"] >= 1)
    client.post("/live/stop")

    events_response = client.get("/live/events?limit=5")
    alerts_response = client.get("/live/alerts?limit=5")
    blocking_response = client.get("/live/blocking?limit=5")
    logs_response = client.get("/live/logs?limit=10")

    assert events_response.status_code == 200
    assert alerts_response.status_code == 200
    assert blocking_response.status_code == 200
    assert logs_response.status_code == 200

    events_payload = events_response.json()
    blocking_payload = blocking_response.json()
    logs_payload = logs_response.json()

    assert "events" in events_payload
    assert events_payload["total_available"] >= 1
    assert events_payload["events"][0]["source"] == "live_runtime"
    assert "alerts" in alerts_response.json()
    assert "blocking_events" in blocking_payload
    assert blocking_payload["total_available"] >= 0
    assert logs_payload["total_available"] >= 1


def test_live_api_exposes_recent_alert_pulse(
    client_with_live,
    packet_factory,
    now_ts,
    replay_waiter,
):
    client, live_runtime_service, manual_capture_service = client_with_live
    original_alert_threshold = live_runtime_service.settings.live_alert_confidence_threshold
    original_block_threshold = live_runtime_service.settings.live_block_confidence_threshold
    object.__setattr__(
        live_runtime_service.settings,
        "live_alert_confidence_threshold",
        0.5,
    )
    object.__setattr__(
        live_runtime_service.settings,
        "live_block_confidence_threshold",
        0.5,
    )

    try:
        start_response = client.post(
            "/live/start",
            json={"interface_name": "test0", "flush_interval_seconds": 60.0},
        )
        assert start_response.status_code == 200

        manual_capture_service.emit_packets(build_api_suspect_packets(now_ts, packet_factory))
        replay_waiter(lambda: client.get("/live/status").json()["alerts"] >= 1)

        pulse_response = client.get("/live/alerts/recent")
        assert pulse_response.status_code == 200
        pulse_payload = pulse_response.json()

        assert pulse_payload["api_exposed_at"]
        assert pulse_payload["latest_alert"] is not None
        assert pulse_payload["latest_alert"]["flow_finalized_at"]
        assert pulse_payload["latest_alert"]["prediction_done_at"]
        assert pulse_payload["latest_alert"]["alert_created_at"]
        assert pulse_payload["latest_alert"]["latency_from_finalization_ms"] is not None

        cursor = pulse_payload["latest_alert"]["alert_created_at"]
        quiet_pulse_response = client.get("/live/alerts/recent", params={"since": cursor})
        assert quiet_pulse_response.status_code == 200
        assert quiet_pulse_response.json()["new_alert_count"] == 0

        client.post("/live/stop")
    finally:
        object.__setattr__(
            live_runtime_service.settings,
            "live_alert_confidence_threshold",
            original_alert_threshold,
        )
        object.__setattr__(
            live_runtime_service.settings,
            "live_block_confidence_threshold",
            original_block_threshold,
        )
