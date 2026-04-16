from __future__ import annotations

from dataclasses import replace
import time

import pytest

from backend.app.core.exceptions import LiveRuntimeError
from backend.app.models.api_models import LiveRuntimeStatus, LiveStartRequest
from backend.app.services.container import build_service_container
from backend.app.services.live_runtime_service import LiveRuntimeService


def build_normal_tcp_packets(now_ts, packet_factory):
    return [
        packet_factory(
            timestamp=now_ts,
            src_ip="10.0.0.10",
            dst_ip="10.0.0.20",
            protocol="TCP",
            src_port=50000,
            dst_port=80,
            packet_length=60,
            syn=1,
        ),
        packet_factory(
            timestamp=now_ts + 0.01,
            src_ip="10.0.0.20",
            dst_ip="10.0.0.10",
            protocol="TCP",
            src_port=80,
            dst_port=50000,
            packet_length=60,
            syn=1,
            ack=1,
        ),
        packet_factory(
            timestamp=now_ts + 0.02,
            src_ip="10.0.0.10",
            dst_ip="10.0.0.20",
            protocol="TCP",
            src_port=50000,
            dst_port=80,
            packet_length=60,
            ack=1,
        ),
        packet_factory(
            timestamp=now_ts + 0.03,
            src_ip="10.0.0.10",
            dst_ip="10.0.0.20",
            protocol="TCP",
            src_port=50000,
            dst_port=80,
            packet_length=400,
            ack=1,
            psh=1,
        ),
        packet_factory(
            timestamp=now_ts + 0.04,
            src_ip="10.0.0.20",
            dst_ip="10.0.0.10",
            protocol="TCP",
            src_port=80,
            dst_port=50000,
            packet_length=200,
            ack=1,
        ),
        packet_factory(
            timestamp=now_ts + 0.05,
            src_ip="10.0.0.10",
            dst_ip="10.0.0.20",
            protocol="TCP",
            src_port=50000,
            dst_port=80,
            packet_length=60,
            ack=1,
            fin=1,
        ),
    ]


def build_suspect_syn_burst_packets(now_ts, packet_factory):
    packets = []
    for offset in range(40):
        packets.append(
            packet_factory(
                timestamp=now_ts + (offset * 0.01),
                src_ip="172.16.0.10",
                dst_ip="172.16.0.20",
                protocol="TCP",
                src_port=45000 + offset,
                dst_port=4400 + offset,
                packet_length=1500,
                syn=1,
                rst=1,
            )
        )
    return packets


def build_half_open_tcp_probe_packets(now_ts, packet_factory):
    return [
        packet_factory(
            timestamp=now_ts,
            src_ip="172.16.1.10",
            dst_ip="172.16.1.20",
            protocol="TCP",
            src_port=55000,
            dst_port=443,
            packet_length=60,
            syn=1,
        ),
        packet_factory(
            timestamp=now_ts + 0.01,
            src_ip="172.16.1.20",
            dst_ip="172.16.1.10",
            protocol="TCP",
            src_port=443,
            dst_port=55000,
            packet_length=60,
            syn=1,
            ack=1,
        ),
    ]


def test_live_runtime_start_stop_and_status(
    live_runtime_service,
    manual_capture_service,
    packet_factory,
    now_ts,
    replay_waiter,
):
    started = live_runtime_service.start(
        LiveStartRequest(interface_name="test0", flush_interval_seconds=0.05)
    )

    assert started.status == LiveRuntimeStatus.RUNNING
    manual_capture_service.emit_packets(build_normal_tcp_packets(now_ts, packet_factory))

    replay_waiter(lambda: live_runtime_service.get_status().predictions >= 1)
    stopped = live_runtime_service.stop()

    assert stopped.status == LiveRuntimeStatus.STOPPED
    assert stopped.packets_captured >= 1
    assert stopped.finalized_flows >= 1
    assert stopped.predictions >= 1


def test_live_runtime_rejects_second_start(live_runtime_service):
    live_runtime_service.start(LiveStartRequest(interface_name="test0"))

    with pytest.raises(LiveRuntimeError):
        live_runtime_service.start(LiveStartRequest(interface_name="test0"))

    live_runtime_service.stop()


def test_live_runtime_counts_parse_errors(
    live_runtime_service,
    manual_capture_service,
    replay_waiter,
):
    live_runtime_service.start(LiveStartRequest(interface_name="test0"))
    manual_capture_service.emit_parse_error()

    replay_waiter(lambda: live_runtime_service.get_status().packet_parse_errors == 1)
    stopped = live_runtime_service.stop()

    assert stopped.packet_parse_errors == 1
    assert stopped.packets_ignored == 1


def test_live_runtime_triggers_blocking_on_suspect_flow(
    live_runtime_service,
    manual_capture_service,
    packet_factory,
    now_ts,
    replay_waiter,
):
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
        live_runtime_service.start(
            LiveStartRequest(interface_name="test0", blocking_mode="dry_run")
        )
        manual_capture_service.emit_packets(build_suspect_syn_burst_packets(now_ts, packet_factory))

        replay_waiter(lambda: live_runtime_service.get_status().block_decisions >= 1)
        stopped = live_runtime_service.stop()

        assert stopped.alerts >= 1
        assert stopped.block_decisions >= 1
        assert stopped.last_predicted_label == "suspect"
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


def test_live_runtime_flushes_immediately_when_packet_finalizes_flow(
    live_runtime_service,
    manual_capture_service,
    packet_factory,
    now_ts,
    replay_waiter,
):
    live_runtime_service.start(
        LiveStartRequest(interface_name="test0", flush_interval_seconds=60.0)
    )
    manual_capture_service.emit_packets(
        build_suspect_syn_burst_packets(now_ts, packet_factory)
    )

    replay_waiter(lambda: live_runtime_service.get_status().predictions >= 1)
    stopped = live_runtime_service.stop()

    assert stopped.predictions >= 1
    assert stopped.finalized_flows >= 1


def test_live_runtime_expires_short_tcp_probe_before_generic_tcp_timeout(
    live_runtime_service,
    manual_capture_service,
    packet_factory,
    now_ts,
    replay_waiter,
):
    live_runtime_service.start(
        LiveStartRequest(interface_name="test0", flush_interval_seconds=0.05)
    )
    manual_capture_service.emit_packets(
        build_half_open_tcp_probe_packets(now_ts, packet_factory)
    )

    replay_waiter(lambda: live_runtime_service.get_status().predictions >= 1)
    stopped = live_runtime_service.stop()

    assert stopped.predictions >= 1
    assert stopped.finalized_flows >= 1


def test_live_runtime_stop_waits_for_batch_flush(
    live_runtime_service,
    manual_capture_service,
    packet_factory,
    now_ts,
    monkeypatch,
):
    original_detect_batch = live_runtime_service.detection_service.detect_flow_batch

    def delayed_detect_batch(**kwargs):
        time.sleep(6.0)
        return original_detect_batch(**kwargs)

    monkeypatch.setattr(
        live_runtime_service.detection_service,
        "detect_flow_batch",
        delayed_detect_batch,
    )

    live_runtime_service.start(
        LiveStartRequest(interface_name="test0", flush_interval_seconds=60.0)
    )
    manual_capture_service.emit_packets(
        build_half_open_tcp_probe_packets(now_ts, packet_factory)
    )

    started_at = time.monotonic()
    stopped = live_runtime_service.stop()
    elapsed = time.monotonic() - started_at

    assert elapsed >= 5.5
    assert stopped.status == LiveRuntimeStatus.STOPPED
    assert stopped.predictions >= 1


def test_live_runtime_stop_freezes_counters(
    live_runtime_service,
    manual_capture_service,
    packet_factory,
    now_ts,
    replay_waiter,
):
    live_runtime_service.start(
        LiveStartRequest(interface_name="test0", flush_interval_seconds=0.05)
    )
    manual_capture_service.emit_packets(build_normal_tcp_packets(now_ts, packet_factory))

    replay_waiter(lambda: live_runtime_service.get_status().predictions >= 1)
    stopped = live_runtime_service.stop()
    counters_after_stop = (
        stopped.packets_captured,
        stopped.finalized_flows,
        stopped.predictions,
        stopped.alerts,
        stopped.block_decisions,
    )

    manual_capture_service.emit_packets(build_normal_tcp_packets(now_ts + 1.0, packet_factory))
    time.sleep(0.2)
    frozen = live_runtime_service.get_status()

    assert frozen.status == LiveRuntimeStatus.STOPPED
    assert (
        frozen.packets_captured,
        frozen.finalized_flows,
        frozen.predictions,
        frozen.alerts,
        frozen.block_decisions,
    ) == counters_after_stop


def test_live_runtime_exposes_recent_event_and_log_history(
    live_runtime_service,
    manual_capture_service,
    packet_factory,
    now_ts,
    replay_waiter,
):
    live_runtime_service.start(
        LiveStartRequest(interface_name="test0", flush_interval_seconds=0.05)
    )
    manual_capture_service.emit_packets(build_normal_tcp_packets(now_ts, packet_factory))

    replay_waiter(lambda: live_runtime_service.get_status().predictions >= 1)
    live_runtime_service.stop()

    events_response = live_runtime_service.get_recent_events(limit=10)
    logs_response = live_runtime_service.get_recent_logs(limit=20)

    assert events_response.total_available >= 1
    event = events_response.events[-1]
    assert event.src_ip == "10.0.0.10"
    assert event.dst_ip == "10.0.0.20"
    assert event.protocol == "TCP"
    assert event.source == "live_runtime"
    assert event.action_taken in {"allow", "alert_only", "block_dry_run"}

    assert logs_response.total_available >= 2
    assert any(log.component == "live_runtime_service" for log in logs_response.logs)


def test_live_runtime_exposes_recent_alert_and_blocking_history(
    live_runtime_service,
    manual_capture_service,
    packet_factory,
    now_ts,
    replay_waiter,
):
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
        live_runtime_service.start(
            LiveStartRequest(interface_name="test0", blocking_mode="dry_run")
        )
        manual_capture_service.emit_packets(
            build_suspect_syn_burst_packets(now_ts, packet_factory)
        )

        replay_waiter(lambda: live_runtime_service.get_status().block_decisions >= 1)
        live_runtime_service.stop()

        alerts_response = live_runtime_service.get_recent_alerts(limit=10)
        blocking_response = live_runtime_service.get_recent_blocking_events(limit=10)

        assert alerts_response.total_available >= 1
        assert blocking_response.total_available >= 1
        assert alerts_response.alerts[-1].severity in {"high", "critical"}
        assert alerts_response.alerts[-1].risk_score is not None
        assert blocking_response.blocking_events[-1].triggered is True
        assert blocking_response.blocking_events[-1].mode == "dry_run"
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


def test_live_runtime_detects_without_dataset_splits(
    settings,
    manual_capture_service,
    packet_factory,
    now_ts,
    replay_waiter,
):
    portable_settings = replace(
        settings,
        train_path=settings.project_root / "missing" / "train.parquet",
        validation_path=settings.project_root / "missing" / "validation.parquet",
        test_path=settings.project_root / "missing" / "test.parquet",
    )
    services = build_service_container(portable_settings)
    services.schema_service.get_contract()
    services.model_service.ensure_model_loaded()
    live_runtime_service = LiveRuntimeService(
        settings=portable_settings,
        schema_service=services.schema_service,
        detection_service=services.detection_service,
        live_capture_service=manual_capture_service,
    )

    live_runtime_service.start(
        LiveStartRequest(interface_name="test0", flush_interval_seconds=0.05)
    )
    manual_capture_service.emit_packets(build_normal_tcp_packets(now_ts, packet_factory))

    replay_waiter(lambda: live_runtime_service.get_status().predictions >= 1)
    stopped = live_runtime_service.stop()

    assert stopped.predictions >= 1
    assert stopped.last_errors == []
