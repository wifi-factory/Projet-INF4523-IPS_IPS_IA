from __future__ import annotations

import pytest

from backend.app.core.exceptions import FeatureContractError


def test_feature_contract_rejects_missing_feature(services, sample_validation_row):
    contract = services.schema_service.get_contract()
    flow_features = {
        column: sample_validation_row[column]
        for column in contract.input_columns_before_encoding
        if column != "protocol"
    }

    with pytest.raises(FeatureContractError):
        services.feature_service.prepare_features(flow_features)
