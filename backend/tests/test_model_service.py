from __future__ import annotations


def test_model_service_loads_existing_model(services):
    info = services.model_service.get_model_info()

    assert info.pipeline_wrapper_type == "Pipeline"
    assert info.model_type == "RandomForestClassifier"
    assert info.feature_count == 31
    assert info.status == "loaded"
    assert info.supports_predict_proba is True
