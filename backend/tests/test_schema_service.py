from __future__ import annotations


def test_metadata_contract_loads(services):
    contract = services.schema_service.get_contract()

    assert contract.model_type == "RandomForestClassifier"
    assert contract.target_column == "label_binary"
    assert contract.positive_label == "suspect"
    assert contract.feature_count == 31
    assert contract.feature_dtypes["protocol"] == "string"
    assert contract.feature_dtypes["src_port"] == "int64"
    assert contract.feature_dtypes["duration_ms"] == "float64"
    assert "src_ip" in contract.excluded_columns
    assert "dst_ip" in contract.excluded_columns
