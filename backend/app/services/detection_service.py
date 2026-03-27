from __future__ import annotations

from ..core.logging import get_logger
from ..models.api_models import FlowDetectionResponse, OperationalMetadata
from ..utils.dataframe_utils import pick_confidence
from ..utils.time_utils import utc_now_iso
from .blocking_service import BlockingService
from .feature_service import FeatureService
from .model_service import ModelService
from .schema_service import SchemaService


class DetectionService:
    def __init__(
        self,
        schema_service: SchemaService,
        feature_service: FeatureService,
        model_service: ModelService,
        blocking_service: BlockingService,
    ) -> None:
        self.schema_service = schema_service
        self.feature_service = feature_service
        self.model_service = model_service
        self.blocking_service = blocking_service
        self.logger = get_logger(self.__class__.__name__)

    def detect_flow(
        self,
        *,
        flow_features: dict[str, object],
        operational_metadata: OperationalMetadata | None = None,
        blocking_mode: str | None = None,
    ) -> FlowDetectionResponse:
        contract = self.schema_service.get_contract()
        prepared = self.feature_service.prepare_features(flow_features)

        predicted_label = self.model_service.predict(prepared.frame)[0]
        probability_rows = self.model_service.predict_proba(prepared.frame)
        probability_map = probability_rows[0] if probability_rows else None
        confidence = pick_confidence(probability_map, predicted_label)

        blocking_decision = self.blocking_service.evaluate(
            predicted_label=predicted_label,
            confidence=confidence,
            operational_metadata=operational_metadata,
            flow_features=flow_features,
            blocking_mode=blocking_mode,
        )
        response = FlowDetectionResponse(
            predicted_label=predicted_label,
            is_suspect=predicted_label == contract.positive_label,
            confidence=confidence,
            probability=probability_map,
            decision_mode="flow_post_classification",
            model_type=contract.model_type,
            target_column=contract.target_column,
            positive_label=contract.positive_label,
            features_used=list(contract.input_columns_before_encoding),
            extra_features_ignored=prepared.extra_features_ignored,
            timestamp_decision=utc_now_iso(),
            blocking_decision=blocking_decision,
        )
        self.logger.info(
            "Flow detected",
            extra={
                "context": {
                    "predicted_label": response.predicted_label,
                    "is_suspect": response.is_suspect,
                    "confidence": response.confidence,
                }
            },
        )
        return response
