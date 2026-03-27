from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BlockingMode(str, Enum):
    DRY_RUN = "dry_run"
    SYSTEM_STUB = "system_stub"


class ReplaySplit(str, Enum):
    VALIDATION = "validation"
    TEST = "test"


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
    is_suspect: bool
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
