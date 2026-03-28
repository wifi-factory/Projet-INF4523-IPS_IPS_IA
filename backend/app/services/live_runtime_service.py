from __future__ import annotations

import threading
from datetime import datetime
from typing import Any
from uuid import uuid4

from ..config import Settings
from ..core.exceptions import LiveRuntimeError
from ..core.logging import get_logger
from ..models.api_models import (
    BlockingMode,
    LiveRuntimeStatus,
    LiveStartRequest,
    LiveStatusResponse,
    OperationalMetadata,
)
from ..utils.time_utils import utc_now, utc_now_iso
from .detection_service import DetectionService
from .flow_aggregation_service import FlowAggregationService, PacketEvent
from .live_capture_service import LiveCaptureService, TsharkCaptureSession
from .schema_service import SchemaService


class LiveRuntimeService:
    def __init__(
        self,
        settings: Settings,
        schema_service: SchemaService,
        detection_service: DetectionService,
        live_capture_service: LiveCaptureService,
    ) -> None:
        self.settings = settings
        self.schema_service = schema_service
        self.detection_service = detection_service
        self.live_capture_service = live_capture_service
        self.logger = get_logger(self.__class__.__name__)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._status = LiveStatusResponse(
            status=LiveRuntimeStatus.STOPPED,
            running=False,
            blocking_mode=BlockingMode(settings.blocking_mode),
            alert_confidence_threshold=settings.live_alert_confidence_threshold,
            block_confidence_threshold=settings.live_block_confidence_threshold,
        )
        self._capture_session: TsharkCaptureSession | None = None
        self._worker: threading.Thread | None = None
        self._aggregator: FlowAggregationService | None = None
        self._pending_rows: list[dict[str, Any]] = []
        self._blocking_mode_value = settings.blocking_mode

    def start(self, request: LiveStartRequest) -> LiveStatusResponse:
        with self._lock:
            if self._is_running_locked():
                raise LiveRuntimeError("A live monitoring session is already running.")

            interface_name = request.interface_name or self.settings.live_default_interface
            if not interface_name:
                raise LiveRuntimeError(
                    "No live interface configured. Provide interface_name or set IPS_LIVE_INTERFACE."
                )

            self.schema_service.get_contract()
            self.detection_service.model_service.ensure_model_loaded()

            session_id = f"LIVE-{uuid4().hex[:8].upper()}"
            capture_id = f"CAP-{session_id}"
            capture_filter = request.capture_filter or self.settings.live_capture_filter
            flush_interval_seconds = (
                request.flush_interval_seconds
                if request.flush_interval_seconds is not None
                else self.settings.live_flush_interval_seconds
            )
            blocking_mode = (
                request.blocking_mode.value
                if request.blocking_mode is not None
                else self.settings.blocking_mode
            )

            self._stop_event = threading.Event()
            self._aggregator = FlowAggregationService(
                self.settings,
                session_id=session_id,
                capture_id=capture_id,
            )
            self._pending_rows = []
            self._blocking_mode_value = blocking_mode
            self._status = LiveStatusResponse(
                status=LiveRuntimeStatus.RUNNING,
                running=True,
                session_id=session_id,
                interface_name=interface_name,
                capture_filter=capture_filter,
                blocking_mode=BlockingMode(blocking_mode),
                alert_confidence_threshold=self.settings.live_alert_confidence_threshold,
                block_confidence_threshold=self.settings.live_block_confidence_threshold,
                started_at=utc_now_iso(),
            )

            try:
                self._capture_session = self.live_capture_service.start_session(
                    interface_name=interface_name,
                    capture_filter=capture_filter,
                    on_packet=self._handle_packet_event,
                    on_error=self._handle_capture_error,
                    on_parse_error=self._handle_parse_error,
                )
            except Exception as exc:
                self._status = self._status.model_copy(
                    update={
                        "status": LiveRuntimeStatus.ERROR,
                        "running": False,
                        "stopped_at": utc_now_iso(),
                        "last_errors": [str(exc)],
                    }
                )
                raise

            self._worker = threading.Thread(
                target=self._run_maintenance_loop,
                args=(flush_interval_seconds,),
                daemon=True,
            )
            self._worker.start()
            return self._snapshot_locked()

    def stop(self) -> LiveStatusResponse:
        with self._lock:
            if not self._is_running_locked():
                return self._snapshot_locked()
            self._status = self._status.model_copy(
                update={
                    "status": LiveRuntimeStatus.STOPPING,
                    "running": True,
                }
            )
            self._stop_event.set()
            capture_session = self._capture_session
            worker = self._worker

        if capture_session is not None:
            capture_session.stop()
        if worker is not None:
            worker.join(timeout=30.0)
            if worker.is_alive():
                self._append_error("Live runtime stop timed out before worker shutdown.")
                with self._lock:
                    self._status = self._status.model_copy(
                        update={
                            "status": LiveRuntimeStatus.ERROR,
                            "running": False,
                            "stopped_at": utc_now_iso(),
                        }
                    )

        return self.get_status()

    def get_status(self) -> LiveStatusResponse:
        with self._lock:
            return self._snapshot_locked()

    def _handle_packet_event(self, packet: PacketEvent) -> None:
        with self._lock:
            if self._stop_event.is_set():
                return
            if self._aggregator is None:
                return
            self._status = self._status.model_copy(
                update={
                    "packets_captured": self._status.packets_captured + 1,
                }
            )
            aggregator = self._aggregator

        try:
            completed = aggregator.ingest_packet(packet)
        except Exception as exc:
            self._append_error(f"Packet aggregation failed: {exc}")
            with self._lock:
                self._status = self._status.model_copy(
                    update={
                        "packets_ignored": self._status.packets_ignored + 1,
                    }
                )
            return

        with self._lock:
            self._pending_rows.extend(completed)
            self._status = self._status.model_copy(
                update={
                    "active_flows": aggregator.active_flow_count(),
                }
            )

    def _handle_capture_error(self, message: str) -> None:
        self._append_error(message)

    def _handle_parse_error(self, message: str) -> None:
        with self._lock:
            if self._stop_event.is_set():
                return
            self._status = self._status.model_copy(
                update={
                    "packets_ignored": self._status.packets_ignored + 1,
                    "packet_parse_errors": self._status.packet_parse_errors + 1,
                }
            )
        self.logger.warning(
            "Live packet parsing failed",
            extra={"context": {"message": message}},
        )

    def _run_maintenance_loop(self, flush_interval_seconds: float) -> None:
        final_status = LiveRuntimeStatus.STOPPED
        try:
            while not self._stop_event.wait(flush_interval_seconds):
                aggregator = self._aggregator
                if aggregator is None:
                    break

                capture_session = self._capture_session
                if capture_session is not None and not capture_session.is_alive():
                    self._append_error("Live capture session stopped unexpectedly.")
                    final_status = LiveRuntimeStatus.ERROR
                    break

                expired_rows = aggregator.expire_flows(utc_now().timestamp())
                with self._lock:
                    self._pending_rows.extend(expired_rows)
                    self._status = self._status.model_copy(
                        update={"active_flows": aggregator.active_flow_count()}
                    )
                self._flush_pending_rows()
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            self._append_error(f"Live maintenance loop failed: {exc}")
            final_status = LiveRuntimeStatus.ERROR
        finally:
            aggregator = self._aggregator
            if aggregator is not None:
                remaining_rows = aggregator.expire_flows(utc_now().timestamp())
                remaining_rows.extend(aggregator.flush_all())
                with self._lock:
                    self._pending_rows.extend(remaining_rows)
                    self._status = self._status.model_copy(
                        update={"active_flows": 0}
                    )
            self._flush_pending_rows()
            with self._lock:
                self._status = self._status.model_copy(
                    update={
                        "status": final_status,
                        "running": False,
                        "stopped_at": utc_now_iso(),
                    }
                )
                self._capture_session = None
                self._worker = None
                self._aggregator = None

    def _flush_pending_rows(self) -> None:
        with self._lock:
            rows = list(self._pending_rows)
            self._pending_rows.clear()
            aggregator = self._aggregator

        if not rows or aggregator is None:
            return

        frame = aggregator.prepare_rows(rows)
        if frame.empty:
            return

        with self._lock:
            self._status = self._status.model_copy(
                update={
                    "finalized_flows": self._status.finalized_flows + int(len(frame)),
                    "active_flows": aggregator.active_flow_count(),
                }
            )

        row_payloads = frame.to_dict(orient="records")
        try:
            results = self.detection_service.detect_flow_batch(
                flow_feature_rows=row_payloads,
                operational_metadata_rows=[
                    self._build_operational_metadata(row) for row in row_payloads
                ],
                blocking_mode=self._blocking_mode_value,
                alert_confidence_threshold=self.settings.live_alert_confidence_threshold,
                block_confidence_threshold=self.settings.live_block_confidence_threshold,
                threshold_source="live_runtime",
            )
        except Exception as exc:
            self._append_error(f"Live detection batch failed: {exc}")
            return

        if not results:
            return

        alerts_increment = sum(1 for result in results if result.is_suspect)
        block_increment = sum(
            1 for result in results if result.blocking_decision.triggered
        )
        last_result = results[-1]
        with self._lock:
            self._status = self._status.model_copy(
                update={
                    "predictions": self._status.predictions + len(results),
                    "alerts": self._status.alerts + alerts_increment,
                    "block_decisions": self._status.block_decisions + block_increment,
                    "last_predicted_label": last_result.predicted_label,
                    "last_confidence": last_result.confidence,
                    "last_event_at": utc_now_iso(),
                }
            )

    def _snapshot_locked(self) -> LiveStatusResponse:
        payload = self._status.model_dump()
        started_at = payload.get("started_at")
        if started_at and payload.get("running"):
            payload["uptime_seconds"] = round(
                (utc_now() - datetime.fromisoformat(started_at)).total_seconds(),
                3,
            )
        elif started_at and payload.get("stopped_at"):
            payload["uptime_seconds"] = round(
                (
                    datetime.fromisoformat(payload["stopped_at"])
                    - datetime.fromisoformat(started_at)
                ).total_seconds(),
                3,
            )
        else:
            payload["uptime_seconds"] = 0.0
        return LiveStatusResponse.model_validate(payload)

    def _append_error(self, message: str) -> None:
        with self._lock:
            errors = list(self._status.last_errors)
            errors.append(message)
            errors = errors[-self.settings.live_status_error_limit :]
            self._status = self._status.model_copy(update={"last_errors": errors})
        self.logger.error(
            "Live runtime error",
            extra={"context": {"message": message}},
        )

    def _is_running_locked(self) -> bool:
        return bool(self._worker and self._worker.is_alive() and self._status.running)

    @staticmethod
    def _build_operational_metadata(row: dict[str, Any]) -> OperationalMetadata:
        return OperationalMetadata(
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
