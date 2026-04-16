from __future__ import annotations

from dataclasses import replace

import pytest

from backend.app.core.exceptions import FeatureContractError
from backend.app.services.container import build_service_container


def test_feature_contract_rejects_missing_feature(services, sample_validation_row):
    contract = services.schema_service.get_contract()
    flow_features = {
        column: sample_validation_row[column]
        for column in contract.input_columns_before_encoding
        if column != "protocol"
    }

    with pytest.raises(FeatureContractError):
        services.feature_service.prepare_features(flow_features)


def test_feature_service_prepares_features_without_dataset_files(
    settings,
    sample_validation_row,
):
    missing_dataset_settings = replace(
        settings,
        train_path=settings.project_root / "missing" / "train.parquet",
        validation_path=settings.project_root / "missing" / "validation.parquet",
        test_path=settings.project_root / "missing" / "test.parquet",
    )
    services = build_service_container(missing_dataset_settings)
    contract = services.schema_service.get_contract()
    flow_features = {
        column: sample_validation_row[column]
        for column in contract.input_columns_before_encoding
    }

    prepared = services.feature_service.prepare_features(flow_features)

    assert list(prepared.frame.columns) == list(contract.input_columns_before_encoding)
    assert prepared.extra_features_ignored == []
