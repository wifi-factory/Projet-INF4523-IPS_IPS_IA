from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BlockingMode(str, Enum):
    DRY_RUN = "dry_run"
    SYSTEM_STUB = "system_stub"
    ENFORCE = "enforce"


class ReplaySplit(str, Enum):
    VALIDATION = "validation"
    TEST = "test"


class LiveRuntimeStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class OperationalMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    flow_id: str | None = None
    capture_id: str | None = None
    session_id: str | None = None
    scenario_id: str | None = None
    scenario_family: str | None = None
    label_family: str | None = None
    severity: str | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    start_ts: float | None = None
    end_ts: float | None = None


class FlowDetectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flow_features: dict[str, Any] = Field(
        ...,
        description="Flow-level ML features aligned to the metadata contract.",
    )
    operational_metadata: OperationalMetadata | None = None
    blocking_mode: BlockingMode | None = None

    @field_validator("flow_features")
    @classmethod
    def validate_flow_features(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("flow_features must contain at least one feature.")
        return value


class BlockingEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    predicted_label: str
    confidence: float | None = None
    probability: dict[str, float] | None = None
    flow_features: dict[str, Any] = Field(default_factory=dict)
    operational_metadata: OperationalMetadata | None = None
    blocking_mode: BlockingMode | None = None


class BlockingDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    action: str = "block"
    triggered: bool
    mode: BlockingMode
    predicted_label: str
    confidence: float | None = None
    threshold_source: str | None = None
    reason: str
    source_ip: str | None = None
    destination_ip: str | None = None
    source_port: int | None = None
    destination_port: int | None = None
    protocol: str | None = None
    created_at: str
    command_preview: str | None = None


class FlowDetectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    predicted_label: str
    raw_predicted_label: str
    is_suspect: bool
    alert_triggered: bool
    block_threshold_met: bool
    confidence: float | None = None
    probability: dict[str, float] | None = None
    decision_mode: str
    model_type: str
    target_column: str
    positive_label: str
    features_used: list[str]
    extra_features_ignored: list[str] = Field(default_factory=list)
    timestamp_decision: str
    blocking_decision: BlockingDecisionResponse


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    model_status: str
    metadata_status: str
    dataset_paths_available: dict[str, bool]
    blocking_mode: BlockingMode
    timestamp: str


class DatasetSplitSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    split: str
    path: str
    rows: int
    columns: int
    dtypes: dict[str, str]
    missing_counts: dict[str, int]
    label_distribution: dict[str, int] | None = None


class DatasetSchemaComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    common_columns: list[str]
    schema_equal_train_validation: bool
    schema_equal_train_test: bool
    columns_only_in_split: dict[str, list[str]]
    dtype_mismatches: list[str]


class DatasetSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    splits: dict[str, DatasetSplitSummary]
    schema_comparison: DatasetSchemaComparison


class ModelInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline_wrapper_type: str
    model_type: str
    target_column: str
    positive_label: str
    feature_count: int
    input_columns: list[str]
    excluded_columns: list[str]
    categorical_columns: list[str]
    numeric_columns: list[str]
    selected_candidate: dict[str, Any]
    model_path: str
    metadata_path: str
    status: str
    supports_predict_proba: bool
    pipeline_steps: list[str]


class ReplayRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    split: ReplaySplit
    limit: int | None = None
    delay_seconds: float | None = None
    pause_between_events: bool = False
    blocking_mode: BlockingMode | None = None

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("limit must be greater than zero.")
        return value

    @field_validator("delay_seconds")
    @classmethod
    def validate_delay(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("delay_seconds must be non-negative.")
        return value


class ReplayStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    split: ReplaySplit | None = None
    requested_limit: int | None = None
    delay_seconds: float = 0.0
    pause_between_events: bool = False
    total_events: int = 0
    processed_events: int = 0
    normal_count: int = 0
    suspect_count: int = 0
    block_decisions_count: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None
    last_event_at: str | None = None


class LiveStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interface_name: str | None = None
    capture_filter: str | None = None
    flush_interval_seconds: float | None = None
    blocking_mode: BlockingMode | None = None

    @field_validator("interface_name")
    @classmethod
    def validate_interface_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("interface_name must not be empty when provided.")
        return stripped

    @field_validator("capture_filter")
    @classmethod
    def validate_capture_filter(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("flush_interval_seconds")
    @classmethod
    def validate_flush_interval(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("flush_interval_seconds must be greater than zero.")
        return value


class LiveStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LiveRuntimeStatus
    running: bool = False
    session_id: str | None = None
    interface_name: str | None = None
    capture_filter: str = ""
    blocking_mode: BlockingMode = BlockingMode.DRY_RUN
    alert_confidence_threshold: float | None = None
    block_confidence_threshold: float | None = None
    started_at: str | None = None
    stopped_at: str | None = None
    last_event_at: str | None = None
    last_alert_at: str | None = None
    uptime_seconds: float = 0.0
    packets_captured: int = 0
    packets_ignored: int = 0
    packet_parse_errors: int = 0
    active_flows: int = 0
    finalized_flows: int = 0
    predictions: int = 0
    alerts: int = 0
    block_decisions: int = 0
    last_predicted_label: str | None = None
    last_confidence: float | None = None
    last_errors: list[str] = Field(default_factory=list)


class LiveInterfaceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: str
    label: str


class LiveInterfacesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interfaces: list[LiveInterfaceInfo] = Field(default_factory=list)


class LiveEventRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    timestamp: str
    src_ip: str
    dst_ip: str
    src_port: int | None = None
    dst_port: int | None = None
    protocol: str
    packet_count: int
    byte_count: int
    duration_ms: float
    tcp_flags: str | None = None
    entropy: float | None = None
    prediction_label: str
    raw_prediction_label: str | None = None
    risk_score: float | None = None
    severity: str
    attack_type: str
    action_taken: str
    status: str
    blocked: bool = False
    flow_id: str | None = None
    source: str = "live_runtime"


class LiveAlertRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: str
    timestamp: str
    attack_type: str
    severity: str
    src_ip: str
    dst_ip: str
    description: str
    recommendation: str
    action_taken: str
    status: str
    risk_score: float | None = None
    flow_started_at: str | None = None
    flow_ended_at: str | None = None
    flow_finalized_at: str | None = None
    prediction_done_at: str | None = None
    alert_created_at: str | None = None
    latency_from_flow_end_ms: float | None = None
    latency_from_finalization_ms: float | None = None


class LiveAlertPulseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "live_runtime_memory"
    api_exposed_at: str
    total_available: int = 0
    new_alert_count: int = 0
    latest_alert: LiveAlertRecordResponse | None = None


class LiveBlockingRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    timestamp: str
    src_ip: str
    dst_ip: str
    src_port: int | None = None
    dst_port: int | None = None
    protocol: str
    predicted_label: str
    confidence: float | None = None
    reason: str
    mode: str
    triggered: bool
    command_preview: str | None = None
    status: str


class LiveLogRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str
    level: str
    component: str
    message: str
    category: str
    source: str


class LiveEventsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "live_runtime_memory"
    total_available: int = 0
    events: list[LiveEventRecordResponse] = Field(default_factory=list)


class LiveAlertsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "live_runtime_memory"
    total_available: int = 0
    alerts: list[LiveAlertRecordResponse] = Field(default_factory=list)


class LiveBlockingHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "live_runtime_memory"
    total_available: int = 0
    blocking_events: list[LiveBlockingRecordResponse] = Field(default_factory=list)


class LiveLogsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "live_runtime_memory"
    total_available: int = 0
    logs: list[LiveLogRecordResponse] = Field(default_factory=list)
