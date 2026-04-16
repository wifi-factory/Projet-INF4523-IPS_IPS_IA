from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from backend.app.config import Settings, get_settings
from backend.app.models.api_models import OperationalMetadata
from backend.app.services.container import build_service_container
from backend.app.services.flow_aggregation_service import PacketEvent
from backend.app.services.live_runtime_service import LiveRuntimeService


INPUT_COLUMNS = [
    "protocol",
    "src_port",
    "dst_port",
    "duration_ms",
    "packet_count_total",
    "packet_count_fwd",
    "packet_count_bwd",
    "byte_count_total",
    "byte_count_fwd",
    "byte_count_bwd",
    "pkt_len_min",
    "pkt_len_max",
    "pkt_len_mean",
    "pkt_len_std",
    "iat_min_ms",
    "iat_max_ms",
    "iat_mean_ms",
    "iat_std_ms",
    "syn_count",
    "ack_count",
    "rst_count",
    "fin_count",
    "psh_count",
    "icmp_echo_req_count",
    "icmp_echo_reply_count",
    "connections_per_1s",
    "connections_per_5s",
    "distinct_dst_ports_per_5s",
    "distinct_dst_ips_per_5s",
    "icmp_packets_per_1s",
    "failed_connection_ratio",
]

EXCLUDED_COLUMNS = [
    "capture_id",
    "dst_ip",
    "end_time",
    "end_ts",
    "flow_id",
    "label_family",
    "scenario_family",
    "scenario_id",
    "session_id",
    "severity",
    "src_ip",
    "start_time",
    "start_ts",
]


def pythonize(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value


def flow_features_from_row(row: pd.Series) -> dict[str, Any]:
    return {column: pythonize(row[column]) for column in INPUT_COLUMNS}


def operational_metadata_from_row(row: pd.Series) -> OperationalMetadata:
    return OperationalMetadata(
        flow_id=pythonize(row["flow_id"]),
        capture_id=pythonize(row["capture_id"]),
        session_id=pythonize(row["session_id"]),
        scenario_id=pythonize(row["scenario_id"]),
        scenario_family=pythonize(row["scenario_family"]),
        label_family=pythonize(row["label_family"]),
        severity=pythonize(row["severity"]),
        src_ip=pythonize(row["src_ip"]),
        dst_ip=pythonize(row["dst_ip"]),
        start_time=pythonize(row["start_time"]),
        end_time=pythonize(row["end_time"]),
        start_ts=pythonize(row["start_ts"]),
        end_ts=pythonize(row["end_ts"]),
    )


def make_flow_row(index: int, label: str, protocol: str) -> dict[str, Any]:
    suspect = label == "suspect"
    base_port = 40000 if suspect else 50000
    dst_port = 4444 if suspect else 80
    duration_ms = 250.0 if suspect else 12.5
    packet_total = 380 if suspect else 12
    packet_fwd = 250 if suspect else 7
    packet_bwd = packet_total - packet_fwd
    byte_total = 64000 if suspect else 1800
    byte_fwd = 42000 if suspect else 1100
    byte_bwd = byte_total - byte_fwd
    pkt_min = 48 if suspect else 60
    pkt_max = 1500 if suspect else 320
    pkt_mean = 420.0 if suspect else 140.0
    pkt_std = 130.0 if suspect else 22.0
    iat_min_ms = 0.1 if suspect else 0.4
    iat_max_ms = 80.0 if suspect else 9.0
    iat_mean_ms = 14.0 if suspect else 1.7
    iat_std_ms = 18.0 if suspect else 0.9
    syn_count = 35 if suspect else 1
    ack_count = 12 if suspect else 5
    rst_count = 3 if suspect else 0
    fin_count = 0 if suspect else 1
    psh_count = 10 if suspect else 0
    icmp_req = 25 if suspect and protocol == "ICMP" else 0
    icmp_reply = 2 if suspect and protocol == "ICMP" else 0
    connections_1s = 45 if suspect else 1
    connections_5s = 160 if suspect else 3
    distinct_ports = 40 if suspect else 1
    distinct_ips = 12 if suspect else 1
    icmp_packets = 30 if suspect and protocol == "ICMP" else 0
    failed_ratio = 0.85 if suspect else 0.0

    return {
        "flow_id": f"flow-{index:03d}",
        "capture_id": f"capture-{index // 2:02d}",
        "session_id": f"session-{index // 3:02d}",
        "scenario_id": f"scenario-{index:02d}",
        "scenario_family": "suspect" if suspect else "normal",
        "start_ts": float(index),
        "end_ts": float(index) + duration_ms / 1000.0,
        "start_time": f"2026-01-01T00:00:{index:02d}Z",
        "end_time": f"2026-01-01T00:00:{index + 1:02d}Z",
        "protocol": protocol,
        "src_ip": f"10.0.0.{index + 1}",
        "dst_ip": "10.0.1.10",
        "src_port": base_port + index,
        "dst_port": dst_port,
        "duration_ms": duration_ms,
        "packet_count_total": packet_total,
        "packet_count_fwd": packet_fwd,
        "packet_count_bwd": packet_bwd,
        "byte_count_total": byte_total,
        "byte_count_fwd": byte_fwd,
        "byte_count_bwd": byte_bwd,
        "pkt_len_min": pkt_min,
        "pkt_len_max": pkt_max,
        "pkt_len_mean": pkt_mean,
        "pkt_len_std": pkt_std,
        "iat_min_ms": iat_min_ms,
        "iat_max_ms": iat_max_ms,
        "iat_mean_ms": iat_mean_ms,
        "iat_std_ms": iat_std_ms,
        "syn_count": syn_count,
        "ack_count": ack_count,
        "rst_count": rst_count,
        "fin_count": fin_count,
        "psh_count": psh_count,
        "icmp_echo_req_count": icmp_req,
        "icmp_echo_reply_count": icmp_reply,
        "connections_per_1s": connections_1s,
        "connections_per_5s": connections_5s,
        "distinct_dst_ports_per_5s": distinct_ports,
        "distinct_dst_ips_per_5s": distinct_ips,
        "icmp_packets_per_1s": icmp_packets,
        "failed_connection_ratio": failed_ratio,
        "label_binary": label,
        "label_family": "scan" if suspect else "benign",
        "severity": "high" if suspect else "low",
    }


def make_scan_row(index: int) -> dict[str, Any]:
    return {
        "flow_id": f"scan-flow-{index:03d}",
        "capture_id": f"scan-capture-{index // 2:02d}",
        "session_id": f"scan-session-{index // 3:02d}",
        "scenario_id": f"scan-scenario-{index:02d}",
        "scenario_family": "suspect",
        "start_ts": float(index),
        "end_ts": float(index),
        "start_time": f"2026-01-01T00:10:{index:02d}Z",
        "end_time": f"2026-01-01T00:10:{index:02d}Z",
        "protocol": "TCP",
        "src_ip": "172.16.0.10",
        "dst_ip": "172.16.0.20",
        "src_port": 45000 + index,
        "dst_port": 4400 + index,
        "duration_ms": 0.0,
        "packet_count_total": 1,
        "packet_count_fwd": 1,
        "packet_count_bwd": 0,
        "byte_count_total": 1500,
        "byte_count_fwd": 1500,
        "byte_count_bwd": 0,
        "pkt_len_min": 1500,
        "pkt_len_max": 1500,
        "pkt_len_mean": 1500.0,
        "pkt_len_std": 0.0,
        "iat_min_ms": 0.0,
        "iat_max_ms": 0.0,
        "iat_mean_ms": 0.0,
        "iat_std_ms": 0.0,
        "syn_count": 1,
        "ack_count": 0,
        "rst_count": 1,
        "fin_count": 0,
        "psh_count": 0,
        "icmp_echo_req_count": 0,
        "icmp_echo_reply_count": 0,
        "connections_per_1s": 40,
        "connections_per_5s": 80,
        "distinct_dst_ports_per_5s": 40,
        "distinct_dst_ips_per_5s": 1,
        "icmp_packets_per_1s": 0,
        "failed_connection_ratio": 1.0,
        "label_binary": "suspect",
        "label_family": "scan",
        "severity": "high",
    }


def build_split_frame(start_index: int, specs: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [make_flow_row(start_index + idx, label, protocol) for idx, (label, protocol) in enumerate(specs)]
    )


def build_runtime_feature_dtypes(frame: pd.DataFrame) -> dict[str, str]:
    return {
        column: ("string" if column == "protocol" else str(frame.dtypes[column]))
        for column in INPUT_COLUMNS
    }


def make_synthetic_artifacts(root: Path) -> dict[str, Any]:
    data_dir = root / "data"
    models_dir = root / "models"
    data_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    train_df = build_split_frame(
        0,
        [
            ("normal", "TCP"),
            ("normal", "UDP"),
            ("normal", "ICMP"),
            ("suspect", "TCP"),
            ("suspect", "UDP"),
            ("suspect", "ICMP"),
            ("normal", "TCP"),
            ("suspect", "TCP"),
        ],
    )
    train_df = pd.concat(
        [train_df, pd.DataFrame([make_scan_row(20 + index) for index in range(6)])],
        ignore_index=True,
    )
    validation_df = build_split_frame(
        100,
        [
            ("normal", "TCP"),
            ("suspect", "TCP"),
            ("normal", "UDP"),
            ("suspect", "ICMP"),
        ],
    )
    validation_df = pd.concat(
        [validation_df, pd.DataFrame([make_scan_row(120), make_scan_row(121)])],
        ignore_index=True,
    )
    test_df = build_split_frame(
        200,
        [
            ("suspect", "TCP"),
            ("normal", "ICMP"),
            ("suspect", "UDP"),
            ("normal", "TCP"),
        ],
    )
    test_df = pd.concat(
        [test_df, pd.DataFrame([make_scan_row(220), make_scan_row(221)])],
        ignore_index=True,
    )

    train_path = data_dir / "05. train.parquet"
    validation_path = data_dir / "06. validation.parquet"
    test_path = data_dir / "04. test.parquet"
    train_df.to_parquet(train_path)
    validation_df.to_parquet(validation_path)
    test_df.to_parquet(test_path)

    numeric_columns = [column for column in INPUT_COLUMNS if column != "protocol"]
    categorical_columns = ["protocol"]
    model = Pipeline(
        steps=[
            (
                "preprocessor",
                ColumnTransformer(
                    transformers=[
                        (
                            "numeric",
                            Pipeline(
                                steps=[("imputer", SimpleImputer(strategy="median"))]
                            ),
                            numeric_columns,
                        ),
                        (
                            "categorical",
                            Pipeline(
                                steps=[
                                    ("imputer", SimpleImputer(strategy="most_frequent")),
                                    ("onehot", OneHotEncoder(handle_unknown="ignore")),
                                ]
                            ),
                            categorical_columns,
                        ),
                    ],
                    remainder="drop",
                ),
            ),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=20,
                    max_depth=5,
                    min_samples_leaf=1,
                    max_features="sqrt",
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(train_df[INPUT_COLUMNS], train_df["label_binary"])
    model_path = models_dir / "random_forest_v1.joblib"
    joblib.dump(model, model_path)

    metadata_path = models_dir / "random_forest_v1_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "model_type": "RandomForestClassifier",
                "target_column": "label_binary",
                "positive_label": "suspect",
                "selected_candidate": {
                    "n_estimators": 20,
                    "max_depth": 5,
                    "min_samples_leaf": 1,
                    "max_features": "sqrt",
                },
                "excluded_columns": EXCLUDED_COLUMNS,
                "input_columns_before_encoding": INPUT_COLUMNS,
                "runtime_feature_dtypes": build_runtime_feature_dtypes(train_df),
                "train_path": str(train_path),
                "validation_path": str(validation_path),
                "test_path": str(test_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "root": root,
        "train_df": train_df,
        "validation_df": validation_df,
        "test_df": test_df,
        "train_path": train_path,
        "validation_path": validation_path,
        "test_path": test_path,
        "model_path": model_path,
        "metadata_path": metadata_path,
    }


class ManualCaptureSession:
    def __init__(self) -> None:
        self._alive = True

    def stop(self) -> None:
        self._alive = False

    def is_alive(self) -> bool:
        return self._alive


class ManualCaptureService:
    def __init__(self) -> None:
        self.interface_name: str | None = None
        self.capture_filter: str | None = None
        self.on_packet = None
        self.on_error = None
        self.on_parse_error = None
        self.session = ManualCaptureSession()
        self.interfaces = [
            ("1", "1. test0"),
            ("2", "2. Wi-Fi"),
        ]

    def list_interfaces(self) -> list[tuple[str, str]]:
        return list(self.interfaces)

    def start_session(self, **kwargs: Any) -> ManualCaptureSession:
        self.interface_name = kwargs["interface_name"]
        self.capture_filter = kwargs.get("capture_filter")
        self.on_packet = kwargs["on_packet"]
        self.on_error = kwargs["on_error"]
        self.on_parse_error = kwargs.get("on_parse_error")
        self.session = ManualCaptureSession()
        return self.session

    def emit_packets(self, packets: list[PacketEvent]) -> None:
        for packet in packets:
            if self.on_packet is not None:
                self.on_packet(packet)

    def emit_parse_error(self, message: str = "synthetic parse error") -> None:
        if self.on_parse_error is not None:
            self.on_parse_error(message)

    def emit_error(self, message: str) -> None:
        if self.on_error is not None:
            self.on_error(message)


@pytest.fixture(scope="session")
def synthetic_artifact_bundle(tmp_path_factory):
    root = tmp_path_factory.mktemp("synthetic_live_artifacts")
    return make_synthetic_artifacts(root)


@pytest.fixture(scope="session")
def settings(synthetic_artifact_bundle) -> Settings:
    return Settings(
        project_root=synthetic_artifact_bundle["root"],
        app_name="Synthetic IPS Backend",
        app_version="test",
        log_level="INFO",
        blocking_mode="dry_run",
        replay_default_delay_seconds=0.0,
        model_path=synthetic_artifact_bundle["model_path"],
        metadata_path=synthetic_artifact_bundle["metadata_path"],
        train_path=synthetic_artifact_bundle["train_path"],
        validation_path=synthetic_artifact_bundle["validation_path"],
        test_path=synthetic_artifact_bundle["test_path"],
        live_default_interface="test0",
        live_capture_filter="ip",
        live_tshark_path="tshark",
        live_flush_interval_seconds=0.05,
        live_tcp_idle_timeout_seconds=0.2,
        live_tcp_probe_timeout_seconds=0.05,
        live_udp_idle_timeout_seconds=0.2,
        live_icmp_idle_timeout_seconds=0.2,
        live_max_flow_duration_seconds=1.0,
        live_alert_confidence_threshold=0.95,
        live_block_confidence_threshold=0.99,
        live_status_error_limit=10,
        live_history_limit=50,
    )


@pytest.fixture(scope="session")
def services(settings):
    container = build_service_container(settings)
    container.schema_service.get_contract()
    container.model_service.ensure_model_loaded()
    return container


@pytest.fixture(scope="session")
def validation_frame(synthetic_artifact_bundle):
    return synthetic_artifact_bundle["validation_df"]


@pytest.fixture(scope="session")
def sample_validation_row(validation_frame):
    return validation_frame.iloc[0]


@pytest.fixture(scope="session")
def sample_suspect_row(validation_frame):
    suspect_rows = validation_frame[validation_frame["label_binary"] == "suspect"]
    return suspect_rows.iloc[0]


@pytest.fixture
def synthetic_env(monkeypatch, synthetic_artifact_bundle):
    monkeypatch.setenv("IPS_MODEL_PATH", str(synthetic_artifact_bundle["model_path"]))
    monkeypatch.setenv("IPS_METADATA_PATH", str(synthetic_artifact_bundle["metadata_path"]))
    monkeypatch.setenv("IPS_TRAIN_PATH", str(synthetic_artifact_bundle["train_path"]))
    monkeypatch.setenv("IPS_VALIDATION_PATH", str(synthetic_artifact_bundle["validation_path"]))
    monkeypatch.setenv("IPS_TEST_PATH", str(synthetic_artifact_bundle["test_path"]))
    monkeypatch.setenv("IPS_BLOCKING_MODE", "dry_run")
    monkeypatch.setenv("IPS_REPLAY_DEFAULT_DELAY_SECONDS", "0.0")
    monkeypatch.setenv("IPS_LIVE_INTERFACE", "test0")
    monkeypatch.setenv("IPS_LIVE_CAPTURE_FILTER", "ip")
    monkeypatch.setenv("IPS_LIVE_FLUSH_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("IPS_LIVE_TCP_IDLE_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setenv("IPS_LIVE_TCP_PROBE_TIMEOUT_SECONDS", "0.05")
    monkeypatch.setenv("IPS_LIVE_UDP_IDLE_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setenv("IPS_LIVE_ICMP_IDLE_TIMEOUT_SECONDS", "0.2")
    monkeypatch.setenv("IPS_LIVE_MAX_FLOW_DURATION_SECONDS", "1.0")
    monkeypatch.setenv("IPS_LIVE_ALERT_CONFIDENCE_THRESHOLD", "0.95")
    monkeypatch.setenv("IPS_LIVE_BLOCK_CONFIDENCE_THRESHOLD", "0.99")
    monkeypatch.setenv("IPS_LIVE_STATUS_ERROR_LIMIT", "10")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def app(synthetic_env):
    from backend.app.main import create_app

    get_settings.cache_clear()
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def manual_capture_service() -> ManualCaptureService:
    return ManualCaptureService()


@pytest.fixture
def live_runtime_service(settings, services, manual_capture_service):
    return LiveRuntimeService(
        settings=settings,
        schema_service=services.schema_service,
        detection_service=services.detection_service,
        live_capture_service=manual_capture_service,
    )


@pytest.fixture
def client_with_live(client, settings, manual_capture_service):
    live_service = LiveRuntimeService(
        settings=settings,
        schema_service=client.app.state.services.schema_service,
        detection_service=client.app.state.services.detection_service,
        live_capture_service=manual_capture_service,
    )
    client.app.state.services.live_capture_service = manual_capture_service
    client.app.state.services.live_runtime_service = live_service
    yield client, live_service, manual_capture_service
    live_service.stop()


@pytest.fixture
def replay_waiter():
    def _wait(predicate, timeout: float = 5.0) -> Any:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(0.02)
        raise AssertionError("Timed out waiting for the expected condition.")

    return _wait


def make_packet(
    *,
    timestamp: float,
    src_ip: str,
    dst_ip: str,
    protocol: str,
    src_port: int = 0,
    dst_port: int = 0,
    packet_length: int = 60,
    syn: int = 0,
    ack: int = 0,
    rst: int = 0,
    fin: int = 0,
    psh: int = 0,
    icmp_type: int = -1,
) -> PacketEvent:
    return PacketEvent(
        timestamp=timestamp,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        protocol=protocol,
        packet_length=packet_length,
        syn=syn,
        ack=ack,
        rst=rst,
        fin=fin,
        psh=psh,
        icmp_type=icmp_type,
    )


@pytest.fixture
def now_ts() -> float:
    return time.time()


@pytest.fixture
def packet_factory():
    return make_packet


def override_settings(base: Settings, **changes: Any) -> Settings:
    return replace(base, **changes)
