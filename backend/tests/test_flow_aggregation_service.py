from __future__ import annotations

from backend.app.services.flow_aggregation_service import FlowAggregationService


def test_flow_aggregation_builds_bidirectional_icmp_flow(settings, packet_factory, now_ts):
    service = FlowAggregationService(settings, session_id="LIVE-TEST", capture_id="CAP-LIVE-TEST")
    completed = []

    completed.extend(
        service.ingest_packet(
            packet_factory(
                timestamp=now_ts,
                src_ip="172.30.1.20",
                dst_ip="172.30.1.21",
                protocol="ICMP",
                packet_length=98,
                icmp_type=8,
            )
        )
    )
    completed.extend(
        service.ingest_packet(
            packet_factory(
                timestamp=now_ts + 0.1,
                src_ip="172.30.1.21",
                dst_ip="172.30.1.20",
                protocol="ICMP",
                packet_length=98,
                icmp_type=0,
            )
        )
    )
    completed.extend(service.flush_all())
    frame = service.prepare_rows(completed)

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["protocol"] == "ICMP"
    assert row["packet_count_total"] == 2
    assert row["packet_count_fwd"] == 1
    assert row["packet_count_bwd"] == 1
    assert row["icmp_echo_req_count"] == 1
    assert row["icmp_echo_reply_count"] == 1
    assert row["connections_per_1s"] == 1


def test_flow_aggregation_finalizes_tcp_flow_on_fin(settings, packet_factory, now_ts):
    service = FlowAggregationService(settings, session_id="LIVE-TEST", capture_id="CAP-LIVE-TEST")
    completed = []

    completed.extend(
        service.ingest_packet(
            packet_factory(
                timestamp=now_ts,
                src_ip="10.0.0.1",
                dst_ip="10.0.0.2",
                protocol="TCP",
                src_port=50000,
                dst_port=80,
                packet_length=60,
                syn=1,
            )
        )
    )
    completed.extend(
        service.ingest_packet(
            packet_factory(
                timestamp=now_ts + 0.05,
                src_ip="10.0.0.2",
                dst_ip="10.0.0.1",
                protocol="TCP",
                src_port=80,
                dst_port=50000,
                packet_length=60,
                ack=1,
            )
        )
    )
    completed.extend(
        service.ingest_packet(
            packet_factory(
                timestamp=now_ts + 0.1,
                src_ip="10.0.0.1",
                dst_ip="10.0.0.2",
                protocol="TCP",
                src_port=50000,
                dst_port=80,
                packet_length=80,
                fin=1,
                ack=1,
            )
        )
    )
    frame = service.prepare_rows(completed)

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["fin_count"] == 1
    assert row["ack_count"] >= 2
    assert row["duration_ms"] > 0


def test_flow_aggregation_computes_scan_window_features(settings, packet_factory, now_ts):
    service = FlowAggregationService(settings, session_id="LIVE-TEST", capture_id="CAP-LIVE-TEST")
    completed = []

    for offset, dst_port in enumerate((22, 80, 443), start=0):
        completed.extend(
            service.ingest_packet(
                packet_factory(
                    timestamp=now_ts + (offset * 0.1),
                    src_ip="192.168.1.10",
                    dst_ip="192.168.1.20",
                    protocol="TCP",
                    src_port=41000 + offset,
                    dst_port=dst_port,
                    packet_length=60,
                    syn=1,
                    rst=1,
                )
            )
        )
    frame = service.prepare_rows(completed)

    assert len(frame) == 3
    last_row = frame.iloc[-1]
    assert last_row["connections_per_1s"] >= 3
    assert last_row["distinct_dst_ports_per_5s"] >= 3
    assert last_row["failed_connection_ratio"] == 1.0
