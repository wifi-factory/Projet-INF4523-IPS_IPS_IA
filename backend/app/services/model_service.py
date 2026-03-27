from __future__ import annotations

from typing import Any

import joblib
import pandas as pd

from ..config import Settings
from ..core.exceptions import ModelLoadError, PredictionError
from ..core.logging import get_logger
from ..models.api_models import ModelInfoResponse
from ..services.schema_service import SchemaService
from ..utils.dataframe_utils import normalize_probability_map


class ModelService:
    def __init__(self, settings: Settings, schema_service: SchemaService) -> None:
        self.settings = settings
        self.schema_service = schema_service
        self.logger = get_logger(self.__class__.__name__)
        self._model: Any | None = None
        self._status = "not_loaded"

    def ensure_model_loaded(self) -> Any:
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def get_status(self) -> str:
        return self._status

    def predict(self, feature_frame: pd.DataFrame) -> list[str]:
        model = self.ensure_model_loaded()
        try:
            return [str(value) for value in model.predict(feature_frame)]
        except Exception as exc:  # pragma: no cover - sklearn detail
            raise PredictionError(f"Model prediction failed: {exc}") from exc

    def predict_proba(
        self,
        feature_frame: pd.DataFrame,
    ) -> list[dict[str, float]] | None:
        model = self.ensure_model_loaded()
        if not hasattr(model, "predict_proba"):
            return None
        try:
            classes = [str(label) for label in model.classes_]
            probabilities = model.predict_proba(feature_frame)
            return [
                normalize_probability_map(row, classes)
                for row in probabilities.tolist()
            ]
        except Exception as exc:  # pragma: no cover - sklearn detail
            raise PredictionError(f"Probability prediction failed: {exc}") from exc

    def get_model_info(self) -> ModelInfoResponse:
        model = self.ensure_model_loaded()
        contract = self.schema_service.get_contract()
        classifier = self._extract_classifier(model)
        return ModelInfoResponse(
            pipeline_wrapper_type=type(model).__name__,
            model_type=type(classifier).__name__,
            target_column=contract.target_column,
            positive_label=contract.positive_label,
            feature_count=contract.feature_count,
            input_columns=list(contract.input_columns_before_encoding),
            excluded_columns=list(contract.excluded_columns),
            categorical_columns=list(contract.categorical_columns),
            numeric_columns=list(contract.numeric_columns),
            selected_candidate=contract.selected_candidate,
            model_path=str(self.settings.model_path),
            metadata_path=str(contract.metadata_path),
            status=self._status,
            supports_predict_proba=hasattr(model, "predict_proba"),
            pipeline_steps=list(getattr(model, "named_steps", {}).keys()),
        )

    def _load_model(self) -> Any:
        contract = self.schema_service.get_contract()
        path = self.settings.model_path
        if not path.exists():
            raise ModelLoadError(f"Model file does not exist: {path}")

        try:
            model = joblib.load(path)
        except Exception as exc:  # pragma: no cover - library-specific detail
            raise ModelLoadError(f"Unable to load model {path}: {exc}") from exc

        classifier = self._extract_classifier(model)
        actual_model_type = type(classifier).__name__
        if actual_model_type != contract.model_type:
            raise ModelLoadError(
                f"Model type mismatch: metadata={contract.model_type}, loaded={actual_model_type}"
            )

        feature_names = getattr(model, "feature_names_in_", None)
        if feature_names is None:
            raise ModelLoadError("Loaded model does not expose feature_names_in_.")

        expected_features = list(contract.input_columns_before_encoding)
        loaded_features = [str(value) for value in feature_names]
        if loaded_features != expected_features:
            raise ModelLoadError(
                "Feature contract mismatch between metadata and loaded model."
            )

        for key, expected_value in contract.selected_candidate.items():
            actual_value = classifier.get_params().get(key)
            if actual_value != expected_value:
                raise ModelLoadError(
                    f"Classifier parameter mismatch for {key}: "
                    f"metadata={expected_value}, loaded={actual_value}"
                )

        self._status = "loaded"
        self.logger.info(
            "Model loaded successfully",
            extra={
                "context": {
                    "model_path": str(path),
                    "wrapper_type": type(model).__name__,
                    "model_type": actual_model_type,
                    "supports_predict_proba": hasattr(model, "predict_proba"),
                }
            },
        )
        return model

    @staticmethod
    def _extract_classifier(model: Any) -> Any:
        if hasattr(model, "named_steps") and "model" in model.named_steps:
            return model.named_steps["model"]
        return model
