from __future__ import annotations


def build_suspicious_e2e_packets(now_ts, packet_factory):
    packets = []
    for offset in range(40):
        packets.append(
            packet_factory(
                timestamp=now_ts + (offset * 0.01),
                src_ip="192.168.50.10",
                dst_ip="192.168.50.20",
                protocol="TCP",
                src_port=49000 + offset,
                dst_port=4400 + offset,
                packet_length=1500,
                syn=1,
                rst=1,
            )
        )
    return packets


def test_live_pipeline_e2e_emits_prediction_and_block_decision(
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
            json={"interface_name": "test0", "blocking_mode": "dry_run"},
        )
        assert start_response.status_code == 200

        manual_capture_service.emit_packets(build_suspicious_e2e_packets(now_ts, packet_factory))

        replay_waiter(
            lambda: client.get("/live/status").json()["block_decisions"] >= 1,
            timeout=8.0,
        )
        status_payload = client.get("/live/status").json()
        stop_payload = client.post("/live/stop").json()

        assert status_payload["finalized_flows"] >= 1
        assert status_payload["predictions"] >= 1
        assert status_payload["alerts"] >= 1
        assert status_payload["block_decisions"] >= 1
        assert stop_payload["status"] == "stopped"
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
