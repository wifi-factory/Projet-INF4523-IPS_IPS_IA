from __future__ import annotations

from unittest.mock import patch

from backend.app.models.api_models import OperationalMetadata


def test_detection_service_predicts_on_validation_row(services, sample_validation_row):
    contract = services.schema_service.get_contract()
    flow_features = {
        column: sample_validation_row[column]
        for column in contract.input_columns_before_encoding
    }
    operational_metadata = OperationalMetadata(
        src_ip=sample_validation_row["src_ip"],
        dst_ip=sample_validation_row["dst_ip"],
        flow_id=sample_validation_row["flow_id"],
    )

    result = services.detection_service.detect_flow(
        flow_features=flow_features,
        operational_metadata=operational_metadata,
    )

    assert result.predicted_label in {"normal", "suspect"}
    assert result.model_type == "RandomForestClassifier"
    assert result.target_column == "label_binary"
    assert len(result.features_used) == 31


def test_detection_service_applies_live_suspect_threshold(
    services,
    sample_validation_row,
):
    contract = services.schema_service.get_contract()
    flow_features = {
        column: sample_validation_row[column]
        for column in contract.input_columns_before_encoding
    }

    with (
        patch.object(
            services.model_service,
            "predict",
            return_value=["suspect"],
        ),
        patch.object(
            services.model_service,
            "predict_proba",
            return_value=[{"normal": 0.09, "suspect": 0.91}],
        ),
    ):
        result = services.detection_service.detect_flow(
            flow_features=flow_features,
            operational_metadata=OperationalMetadata(src_ip="10.0.0.1", dst_ip="10.0.0.2"),
            alert_confidence_threshold=0.96,
            block_confidence_threshold=0.99,
            threshold_source="live_runtime",
        )

    assert result.predicted_label == "normal"
    assert result.raw_predicted_label == "suspect"
    assert result.is_suspect is False
    assert result.alert_triggered is False
    assert result.block_threshold_met is False
    assert result.blocking_decision.triggered is False


def test_detection_service_supports_alert_only_suspect(
    services,
    sample_validation_row,
):
    contract = services.schema_service.get_contract()
    flow_features = {
        column: sample_validation_row[column]
        for column in contract.input_columns_before_encoding
    }

    with (
        patch.object(
            services.model_service,
            "predict",
            return_value=["suspect"],
        ),
        patch.object(
            services.model_service,
            "predict_proba",
            return_value=[{"normal": 0.03, "suspect": 0.97}],
        ),
    ):
        result = services.detection_service.detect_flow(
            flow_features=flow_features,
            operational_metadata=OperationalMetadata(src_ip="10.0.0.1", dst_ip="10.0.0.2"),
            alert_confidence_threshold=0.95,
            block_confidence_threshold=0.99,
            threshold_source="live_runtime",
        )

    assert result.predicted_label == "suspect"
    assert result.raw_predicted_label == "suspect"
    assert result.is_suspect is True
    assert result.alert_triggered is True
    assert result.block_threshold_met is False
    assert result.blocking_decision.triggered is False
    assert result.blocking_decision.reason == "suspect classification below block confidence threshold"
