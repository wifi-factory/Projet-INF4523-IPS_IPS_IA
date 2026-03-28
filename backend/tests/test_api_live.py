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
