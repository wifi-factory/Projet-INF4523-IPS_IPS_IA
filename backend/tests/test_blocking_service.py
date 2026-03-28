from __future__ import annotations

from backend.app.models.api_models import BlockingMode
from backend.app.models.api_models import OperationalMetadata


def test_blocking_service_triggers_dry_run_for_suspect(services, sample_suspect_row):
    contract = services.schema_service.get_contract()
    flow_features = {
        column: sample_suspect_row[column]
        for column in contract.input_columns_before_encoding
    }
    operational_metadata = OperationalMetadata(
        src_ip=sample_suspect_row["src_ip"],
        dst_ip=sample_suspect_row["dst_ip"],
    )

    decision = services.blocking_service.evaluate(
        predicted_label="suspect",
        confidence=0.95,
        operational_metadata=operational_metadata,
        flow_features=flow_features,
        blocking_mode="dry_run",
    )

    assert decision.triggered is True
    assert decision.mode.value == "dry_run"
    assert decision.reason == "post-flow-classification suspect decision"
    assert decision.source_ip == sample_suspect_row["src_ip"]


def test_blocking_service_enforce_falls_back_to_dry_run_on_failure(
    services,
    sample_suspect_row,
    monkeypatch,
):
    contract = services.schema_service.get_contract()
    flow_features = {
        column: sample_suspect_row[column]
        for column in contract.input_columns_before_encoding
    }
    operational_metadata = OperationalMetadata(
        src_ip=sample_suspect_row["src_ip"],
        dst_ip=sample_suspect_row["dst_ip"],
    )

    monkeypatch.setattr(
        "backend.app.services.blocking_service.apply_firewall_command",
        lambda command: (False, "Firewall enforcement is only supported on Linux."),
    )

    decision = services.blocking_service.evaluate(
        predicted_label="suspect",
        confidence=0.95,
        operational_metadata=operational_metadata,
        flow_features=flow_features,
        blocking_mode=BlockingMode.ENFORCE,
    )

    assert decision.triggered is True
    assert decision.mode == BlockingMode.DRY_RUN
    assert decision.reason == "Firewall enforcement is only supported on Linux."
