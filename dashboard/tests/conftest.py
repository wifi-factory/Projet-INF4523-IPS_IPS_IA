from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dashboard.services.live_provider import PagePayload, RuntimeControlPayload


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def sample_payload() -> PagePayload:
    events_df = pd.DataFrame(
        [
            {
                "Heure": "16:42:16",
                "Label": "Suspect",
                "Score": "0.99",
                "Proto": "TCP",
                "Source": "172.30.1.21",
                "Destination": "172.30.1.24",
                "Port src": 44712,
                "Port dst": 22,
                "Action": "Blocage",
                "Statut": "Ouverte",
            },
            {
                "Heure": "16:42:13",
                "Label": "Normal",
                "Score": "0.07",
                "Proto": "ICMP",
                "Source": "172.30.1.23",
                "Destination": "172.30.1.24",
                "Port src": 0,
                "Port dst": 0,
                "Action": "Autoriser",
                "Statut": "Fermee",
            },
        ]
    )
    alerts_df = pd.DataFrame(
        [
            {
                "Heure": "16:41:57",
                "Severite": "Critique",
                "Type": "Scan TCP",
                "Source": "172.30.1.21",
                "Destination": "172.30.1.24",
                "Action": "Blocage",
                "Statut": "Ouverte",
                "Score": "0.99",
            }
        ]
    )
    logs_df = pd.DataFrame(
        [
            {
                "Heure": "16:42:18",
                "Niveau": "INFO",
                "Type": "Runtime",
                "Message": "Capture active",
            },
            {
                "Heure": "16:42:17",
                "Niveau": "BLOCAGE",
                "Type": "Action",
                "Message": "Blocage declenche",
            },
        ]
    )
    return PagePayload(
        backend_ok=True,
        backend_status="OK",
        backend_error=None,
        live_status={
            "status": "running",
            "session_id": "LIVE-TEST1234",
            "interface_name": "eth0",
            "capture_filter": "host 172.30.1.24",
            "uptime_seconds": 123.0,
            "packets_captured": 3842,
            "packet_parse_errors": 0,
            "active_flows": 21,
            "finalized_flows": 1284,
            "predictions": 1284,
            "alerts": 37,
            "block_decisions": 19,
            "last_event_at": "2026-04-03T16:42:18",
            "last_errors": [],
            "running": True,
        },
        dataframes={
            "events": events_df,
            "alerts": alerts_df,
            "logs": logs_df,
            "journal": logs_df,
            "blocking": pd.DataFrame(),
        },
        summaries={
            "runtime_label": "RUNNING",
            "finalized_flows": "1 284",
            "alerts": "37",
            "blocking": "19",
            "suspect_rate": "2,9 %",
            "critical_count": 1,
            "high_count": 0,
            "medium_count": 0,
            "unique_sources": 1,
            "recent_alert": alerts_df.iloc[0].to_dict(),
            "blocking_count": 19,
            "normal_count": 1,
            "suspect_count": 1,
            "mean_suspect_score": "0.99",
            "protocol_count": 2,
            "selected_event": events_df.iloc[0].to_dict(),
            "line_count": 2,
            "info_count": 1,
            "alert_count": 0,
            "focus": logs_df.iloc[0].to_dict(),
        },
    )


@pytest.fixture
def runtime_control_payload(sample_payload: PagePayload) -> RuntimeControlPayload:
    return RuntimeControlPayload(
        backend_ok=sample_payload.backend_ok,
        backend_status=sample_payload.backend_status,
        backend_error=sample_payload.backend_error,
        interfaces_error=None,
        live_status=sample_payload.live_status,
        interfaces=[
            {"index": "1", "label": "eth0"},
            {"index": "2", "label": "eth1"},
        ],
    )
