from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings, get_settings
from .blocking_service import BlockingService
from .dataset_service import DatasetService
from .detection_service import DetectionService
from .feature_service import FeatureService
from .live_capture_service import LiveCaptureService
from .live_runtime_service import LiveRuntimeService
from .model_service import ModelService
from .replay_service import ReplayService
from .schema_service import SchemaService


@dataclass
class ServiceContainer:
    settings: Settings
    schema_service: SchemaService
    dataset_service: DatasetService
    feature_service: FeatureService
    model_service: ModelService
    blocking_service: BlockingService
    detection_service: DetectionService
    replay_service: ReplayService
    live_capture_service: LiveCaptureService
    live_runtime_service: LiveRuntimeService


def build_service_container(settings: Settings | None = None) -> ServiceContainer:
    resolved_settings = settings or get_settings()
    schema_service = SchemaService(resolved_settings)
    dataset_service = DatasetService(resolved_settings)
    feature_service = FeatureService(schema_service, dataset_service)
    model_service = ModelService(resolved_settings, schema_service)
    blocking_service = BlockingService(resolved_settings, schema_service)
    detection_service = DetectionService(
        schema_service=schema_service,
        feature_service=feature_service,
        model_service=model_service,
        blocking_service=blocking_service,
    )
    replay_service = ReplayService(
        settings=resolved_settings,
        schema_service=schema_service,
        dataset_service=dataset_service,
        detection_service=detection_service,
    )
    live_capture_service = LiveCaptureService(resolved_settings)
    live_runtime_service = LiveRuntimeService(
        settings=resolved_settings,
        schema_service=schema_service,
        detection_service=detection_service,
        live_capture_service=live_capture_service,
    )
    return ServiceContainer(
        settings=resolved_settings,
        schema_service=schema_service,
        dataset_service=dataset_service,
        feature_service=feature_service,
        model_service=model_service,
        blocking_service=blocking_service,
        detection_service=detection_service,
        replay_service=replay_service,
        live_capture_service=live_capture_service,
        live_runtime_service=live_runtime_service,
    )
