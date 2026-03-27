from __future__ import annotations

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
