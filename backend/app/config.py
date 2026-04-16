from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_MODEL_DIR = PROJECT_ROOT / "models"
LOCAL_LAB_V2_PREPARED_DIR = (
    PROJECT_ROOT / "data" / "lab_v2" / "prepared" / "lab_v2_balanced_v2_20260328_1310"
)


def resolve_configured_path(value: str | None, default_path: Path) -> Path:
    if not value:
        return default_path

    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


@dataclass(frozen=True)
class Settings:
    project_root: Path
    app_name: str
    app_version: str
    log_level: str
    blocking_mode: str
    replay_default_delay_seconds: float
    model_path: Path
    metadata_path: Path
    train_path: Path
    validation_path: Path
    test_path: Path
    live_default_interface: str | None
    live_capture_filter: str
    live_tshark_path: str
    live_flush_interval_seconds: float
    live_tcp_idle_timeout_seconds: float
    live_tcp_probe_timeout_seconds: float
    live_udp_idle_timeout_seconds: float
    live_icmp_idle_timeout_seconds: float
    live_max_flow_duration_seconds: float
    live_alert_confidence_threshold: float
    live_block_confidence_threshold: float
    live_status_error_limit: int
    live_history_limit: int

    @property
    def dataset_paths(self) -> dict[str, Path]:
        return {
            "train": self.train_path,
            "validation": self.validation_path,
            "test": self.test_path,
        }


def build_settings() -> Settings:
    default_model_path = LOCAL_MODEL_DIR / "random_forest_lab_v2.joblib"
    default_metadata_path = LOCAL_MODEL_DIR / "random_forest_lab_v2_metadata.json"
    default_train_path = LOCAL_LAB_V2_PREPARED_DIR / "train_balanced.parquet"
    default_validation_path = LOCAL_LAB_V2_PREPARED_DIR / "validation_clean.parquet"
    default_test_path = LOCAL_LAB_V2_PREPARED_DIR / "test_clean.parquet"

    return Settings(
        project_root=PROJECT_ROOT,
        app_name="Projet INF4523 - IPS IA Backend",
        app_version="0.1.0",
        log_level=os.getenv("IPS_LOG_LEVEL", "INFO"),
        blocking_mode=os.getenv("IPS_BLOCKING_MODE", "dry_run"),
        replay_default_delay_seconds=float(
            os.getenv("IPS_REPLAY_DEFAULT_DELAY_SECONDS", "0.0")
        ),
        model_path=resolve_configured_path(
            os.getenv("IPS_MODEL_PATH"),
            default_model_path,
        ),
        metadata_path=resolve_configured_path(
            os.getenv("IPS_METADATA_PATH"),
            default_metadata_path,
        ),
        train_path=resolve_configured_path(
            os.getenv("IPS_TRAIN_PATH"),
            default_train_path,
        ),
        validation_path=resolve_configured_path(
            os.getenv("IPS_VALIDATION_PATH"),
            default_validation_path,
        ),
        test_path=resolve_configured_path(
            os.getenv("IPS_TEST_PATH"),
            default_test_path,
        ),
        live_default_interface=os.getenv("IPS_LIVE_INTERFACE") or None,
        live_capture_filter=os.getenv("IPS_LIVE_CAPTURE_FILTER", "ip"),
        live_tshark_path=os.getenv("IPS_LIVE_TSHARK_PATH", "tshark"),
        live_flush_interval_seconds=float(
            os.getenv("IPS_LIVE_FLUSH_INTERVAL_SECONDS", "0.5")
        ),
        live_tcp_idle_timeout_seconds=float(
            os.getenv("IPS_LIVE_TCP_IDLE_TIMEOUT_SECONDS", "30.0")
        ),
        live_tcp_probe_timeout_seconds=float(
            os.getenv("IPS_LIVE_TCP_PROBE_TIMEOUT_SECONDS", "3.0")
        ),
        live_udp_idle_timeout_seconds=float(
            os.getenv("IPS_LIVE_UDP_IDLE_TIMEOUT_SECONDS", "15.0")
        ),
        live_icmp_idle_timeout_seconds=float(
            os.getenv("IPS_LIVE_ICMP_IDLE_TIMEOUT_SECONDS", "5.0")
        ),
        live_max_flow_duration_seconds=float(
            os.getenv("IPS_LIVE_MAX_FLOW_DURATION_SECONDS", "60.0")
        ),
        live_alert_confidence_threshold=float(
            os.getenv(
                "IPS_LIVE_ALERT_CONFIDENCE_THRESHOLD",
                os.getenv("IPS_LIVE_SUSPECT_CONFIDENCE_THRESHOLD", "0.95"),
            )
        ),
        live_block_confidence_threshold=float(
            os.getenv("IPS_LIVE_BLOCK_CONFIDENCE_THRESHOLD", "0.99")
        ),
        live_status_error_limit=int(
            os.getenv("IPS_LIVE_STATUS_ERROR_LIMIT", "20")
        ),
        live_history_limit=int(
            os.getenv("IPS_LIVE_HISTORY_LIMIT", "250")
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return build_settings()
