from __future__ import annotations

import threading
import time
from typing import Any

from ..config import Settings
from ..core.exceptions import ReplayError
from ..core.logging import get_logger
from ..models.api_models import (
    OperationalMetadata,
    ReplayRunRequest,
    ReplayStatusResponse,
)
from ..utils.time_utils import utc_now_iso
from .dataset_service import DatasetService
from .detection_service import DetectionService
from .schema_service import SchemaService


class ReplayService:
    def __init__(
        self,
        settings: Settings,
        schema_service: SchemaService,
        dataset_service: DatasetService,
        detection_service: DetectionService,
    ) -> None:
        self.settings = settings
        self.schema_service = schema_service
        self.dataset_service = dataset_service
        self.detection_service = detection_service
        self.logger = get_logger(self.__class__.__name__)
        self._lock = threading.Lock()
        self._status = ReplayStatusResponse(status="idle")
        self._worker: threading.Thread | None = None

    def run(self, request: ReplayRunRequest) -> ReplayStatusResponse:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                raise ReplayError("A replay is already running.")

            delay_seconds = (
                request.delay_seconds
                if request.delay_seconds is not None
                else self.settings.replay_default_delay_seconds
            )
            self._status = ReplayStatusResponse(
                status="running",
                split=request.split,
                requested_limit=request.limit,
                delay_seconds=delay_seconds,
                pause_between_events=request.pause_between_events,
                started_at=utc_now_iso(),
            )
            self._worker = threading.Thread(
                target=self._run_worker,
                args=(request, delay_seconds),
                daemon=True,
            )
            self._worker.start()
            return self._status.model_copy(deep=True)

    def get_status(self) -> ReplayStatusResponse:
        with self._lock:
            return self._status.model_copy(deep=True)

    def _run_worker(self, request: ReplayRunRequest, delay_seconds: float) -> None:
        contract = self.schema_service.get_contract()
        try:
            frame = self.dataset_service.load_split(request.split.value)
            if request.limit is not None:
                frame = frame.head(request.limit)

            self._update_status(total_events=int(len(frame)))
            for _, row in frame.iterrows():
                flow_features = {
                    column: row[column]
                    for column in contract.input_columns_before_encoding
                }
                operational_metadata = OperationalMetadata(
                    flow_id=row.get("flow_id"),
                    capture_id=row.get("capture_id"),
                    session_id=row.get("session_id"),
                    scenario_id=row.get("scenario_id"),
                    scenario_family=row.get("scenario_family"),
                    label_family=row.get("label_family"),
                    severity=row.get("severity"),
                    src_ip=row.get("src_ip"),
                    dst_ip=row.get("dst_ip"),
                    start_time=row.get("start_time"),
                    end_time=row.get("end_time"),
                    start_ts=row.get("start_ts"),
                    end_ts=row.get("end_ts"),
                )
                result = self.detection_service.detect_flow(
                    flow_features=flow_features,
                    operational_metadata=operational_metadata,
                    blocking_mode=(
                        request.blocking_mode.value
                        if request.blocking_mode is not None
                        else None
                    ),
                )
                self._accumulate_result(result.model_dump())

                if request.pause_between_events and delay_seconds > 0:
                    time.sleep(delay_seconds)

            self._finalize(status="completed")
        except Exception as exc:
            self.logger.exception("Replay execution failed")
            self._finalize(status="failed", error=str(exc))

    def _accumulate_result(self, result: dict[str, Any]) -> None:
        with self._lock:
            processed_events = self._status.processed_events + 1
            normal_count = self._status.normal_count
            suspect_count = self._status.suspect_count
            block_decisions_count = self._status.block_decisions_count

            if result["is_suspect"]:
                suspect_count += 1
            else:
                normal_count += 1
            if result["blocking_decision"]["triggered"]:
                block_decisions_count += 1

            self._status = self._status.model_copy(
                update={
                    "processed_events": processed_events,
                    "normal_count": normal_count,
                    "suspect_count": suspect_count,
                    "block_decisions_count": block_decisions_count,
                    "last_event_at": utc_now_iso(),
                }
            )

    def _update_status(self, **kwargs: Any) -> None:
        with self._lock:
            self._status = self._status.model_copy(update=kwargs)

    def _finalize(self, *, status: str, error: str | None = None) -> None:
        with self._lock:
            errors = list(self._status.errors)
            if error:
                errors.append(error)
            self._status = self._status.model_copy(
                update={
                    "status": status,
                    "errors": errors,
                    "completed_at": utc_now_iso(),
                }
            )
