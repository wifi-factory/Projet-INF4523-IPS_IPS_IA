from __future__ import annotations

from typing import Mapping, Sequence

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
        alert_confidence_threshold: float | None = None,
        block_confidence_threshold: float | None = None,
        threshold_source: str | None = None,
    ) -> FlowDetectionResponse:
        contract = self.schema_service.get_contract()
        prepared = self.feature_service.prepare_features(flow_features)

        raw_predicted_label = self.model_service.predict(prepared.frame)[0]
        probability_rows = self.model_service.predict_proba(prepared.frame)
        probability_map = probability_rows[0] if probability_rows else None
        confidence = pick_confidence(probability_map, raw_predicted_label)
        predicted_label = self._apply_suspect_threshold(
            predicted_label=raw_predicted_label,
            probability_map=probability_map,
            positive_label=contract.positive_label,
            threshold=alert_confidence_threshold,
        )
        alert_triggered = predicted_label == contract.positive_label
        block_threshold_met = self._meets_suspect_threshold(
            predicted_label=predicted_label,
            probability_map=probability_map,
            positive_label=contract.positive_label,
            threshold=block_confidence_threshold,
        )

        blocking_decision = self.blocking_service.evaluate(
            predicted_label=predicted_label,
            confidence=confidence,
            operational_metadata=operational_metadata,
            flow_features=flow_features,
            blocking_mode=blocking_mode,
            block_threshold_met=block_threshold_met,
            threshold_source=threshold_source,
        )
        response = FlowDetectionResponse(
            predicted_label=predicted_label,
            raw_predicted_label=raw_predicted_label,
            is_suspect=alert_triggered,
            alert_triggered=alert_triggered,
            block_threshold_met=block_threshold_met,
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

    def detect_flow_batch(
        self,
        *,
        flow_feature_rows: Sequence[Mapping[str, object]],
        operational_metadata_rows: Sequence[OperationalMetadata | None] | None = None,
        blocking_mode: str | None = None,
        alert_confidence_threshold: float | None = None,
        block_confidence_threshold: float | None = None,
        threshold_source: str | None = None,
    ) -> list[FlowDetectionResponse]:
        if not flow_feature_rows:
            return []

        contract = self.schema_service.get_contract()
        metadata_rows = (
            list(operational_metadata_rows)
            if operational_metadata_rows is not None
            else [None] * len(flow_feature_rows)
        )
        if len(metadata_rows) != len(flow_feature_rows):
            raise ValueError(
                "operational_metadata_rows must align with flow_feature_rows."
            )

        prepared_frame = self.feature_service.prepare_feature_frame(flow_feature_rows)
        predicted_labels = self.model_service.predict(prepared_frame)
        probability_rows = self.model_service.predict_proba(prepared_frame)

        responses: list[FlowDetectionResponse] = []
        for index, (flow_features, operational_metadata, raw_predicted_label) in enumerate(
            zip(flow_feature_rows, metadata_rows, predicted_labels, strict=True)
        ):
            probability_map = probability_rows[index] if probability_rows else None
            confidence = pick_confidence(probability_map, raw_predicted_label)
            predicted_label = self._apply_suspect_threshold(
                predicted_label=raw_predicted_label,
                probability_map=probability_map,
                positive_label=contract.positive_label,
                threshold=alert_confidence_threshold,
            )
            alert_triggered = predicted_label == contract.positive_label
            block_threshold_met = self._meets_suspect_threshold(
                predicted_label=predicted_label,
                probability_map=probability_map,
                positive_label=contract.positive_label,
                threshold=block_confidence_threshold,
            )
            blocking_decision = self.blocking_service.evaluate(
                predicted_label=predicted_label,
                confidence=confidence,
                operational_metadata=operational_metadata,
                flow_features=flow_features,
                blocking_mode=blocking_mode,
                block_threshold_met=block_threshold_met,
                threshold_source=threshold_source,
            )
            response = FlowDetectionResponse(
                predicted_label=predicted_label,
                raw_predicted_label=raw_predicted_label,
                is_suspect=alert_triggered,
                alert_triggered=alert_triggered,
                block_threshold_met=block_threshold_met,
                confidence=confidence,
                probability=probability_map,
                decision_mode="flow_post_classification",
                model_type=contract.model_type,
                target_column=contract.target_column,
                positive_label=contract.positive_label,
                features_used=list(contract.input_columns_before_encoding),
                extra_features_ignored=[],
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
            responses.append(response)

        return responses

    @staticmethod
    def _apply_suspect_threshold(
        *,
        predicted_label: str,
        probability_map: dict[str, float] | None,
        positive_label: str,
        threshold: float | None,
    ) -> str:
        if (
            threshold is None
            or probability_map is None
            or predicted_label != positive_label
        ):
            return predicted_label

        positive_probability = float(probability_map.get(positive_label, 0.0))
        if positive_probability >= threshold:
            return predicted_label

        fallback_labels = [
            label for label in probability_map.keys() if label != positive_label
        ]
        if not fallback_labels:
            return "normal"
        return max(fallback_labels, key=lambda label: float(probability_map[label]))

    @staticmethod
    def _meets_suspect_threshold(
        *,
        predicted_label: str,
        probability_map: dict[str, float] | None,
        positive_label: str,
        threshold: float | None,
    ) -> bool:
        if predicted_label != positive_label:
            return False
        if threshold is None or probability_map is None:
            return True
        return float(probability_map.get(positive_label, 0.0)) >= threshold
