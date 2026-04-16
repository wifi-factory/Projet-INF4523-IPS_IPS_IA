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
    FlowDetectionResponse,
    LiveAlertRecordResponse,
    LiveAlertPulseResponse,
    LiveAlertsResponse,
    LiveBlockingHistoryResponse,
    LiveBlockingRecordResponse,
    LiveEventRecordResponse,
    LiveEventsResponse,
    LiveLogRecordResponse,
    LiveLogsResponse,
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
        self._recent_events: list[LiveEventRecordResponse] = []
        self._recent_alerts: list[LiveAlertRecordResponse] = []
        self._recent_blocking: list[LiveBlockingRecordResponse] = []
        self._recent_logs: list[LiveLogRecordResponse] = []

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
            self._reset_history_locked()
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
            self._record_log_locked(
                level="INFO",
                component="live_runtime_service",
                message=(
                    f"Live session {session_id} started on interface "
                    f"{interface_name} in {blocking_mode} mode."
                ),
                category="runtime",
            )
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

    def get_recent_events(self, limit: int = 100) -> LiveEventsResponse:
        with self._lock:
            return LiveEventsResponse(
                total_available=len(self._recent_events),
                events=list(self._recent_events[-limit:]),
            )

    def get_recent_alerts(self, limit: int = 100) -> LiveAlertsResponse:
        with self._lock:
            return LiveAlertsResponse(
                total_available=len(self._recent_alerts),
                alerts=list(self._recent_alerts[-limit:]),
            )

    def get_recent_alert_pulse(self, since: str | None = None) -> LiveAlertPulseResponse:
        with self._lock:
            alerts = list(self._recent_alerts)

        latest_alert = alerts[-1] if alerts else None
        if since is None:
            new_alert_count = 1 if latest_alert is not None else 0
        else:
            new_alert_count = sum(
                1
                for alert in alerts
                if self._is_timestamp_after(
                    alert.alert_created_at or alert.timestamp,
                    since,
                )
            )

        return LiveAlertPulseResponse(
            api_exposed_at=utc_now_iso(),
            total_available=len(alerts),
            new_alert_count=new_alert_count,
            latest_alert=latest_alert,
        )

    def get_recent_blocking_events(
        self,
        limit: int = 100,
    ) -> LiveBlockingHistoryResponse:
        with self._lock:
            return LiveBlockingHistoryResponse(
                total_available=len(self._recent_blocking),
                blocking_events=list(self._recent_blocking[-limit:]),
            )

    def get_recent_logs(self, limit: int = 100) -> LiveLogsResponse:
        with self._lock:
            return LiveLogsResponse(
                total_available=len(self._recent_logs),
                logs=list(self._recent_logs[-limit:]),
            )

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

        if completed:
            self._flush_pending_rows()

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
                if (
                    capture_session is not None
                    and not capture_session.is_alive()
                    and not self._stop_event.is_set()
                ):
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
                self._record_log_locked(
                    level="INFO" if final_status == LiveRuntimeStatus.STOPPED else "ERROR",
                    component="live_runtime_service",
                    message=(
                        f"Live session stopped with status {final_status.value}. "
                        f"Predictions={self._status.predictions}, alerts={self._status.alerts}, "
                        f"blocks={self._status.block_decisions}."
                    ),
                    category="runtime",
                )

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
        metadata_rows = [
            self._build_operational_metadata(row) for row in row_payloads
        ]
        try:
            results = self.detection_service.detect_flow_batch(
                flow_feature_rows=row_payloads,
                operational_metadata_rows=metadata_rows,
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
        last_alert_at = next(
            (
                result.timestamp_decision
                for result in reversed(results)
                if result.alert_triggered
            ),
            None,
        )
        with self._lock:
            self._status = self._status.model_copy(
                update={
                    "predictions": self._status.predictions + len(results),
                    "alerts": self._status.alerts + alerts_increment,
                    "block_decisions": self._status.block_decisions + block_increment,
                    "last_predicted_label": last_result.predicted_label,
                    "last_confidence": last_result.confidence,
                    "last_event_at": utc_now_iso(),
                    "last_alert_at": last_alert_at or self._status.last_alert_at,
                }
            )

        for row_payload, operational_metadata, result in zip(
            row_payloads,
            metadata_rows,
            results,
            strict=True,
        ):
            event_record = self._build_event_record(
                row_payload=row_payload,
                operational_metadata=operational_metadata,
                result=result,
            )
            self._append_history_item(self._recent_events, event_record)

            if result.alert_triggered:
                alert_record = self._build_alert_record(
                    event_record=event_record,
                    row_payload=row_payload,
                    result=result,
                )
                self._append_history_item(self._recent_alerts, alert_record)
                self._record_log(
                    level="WARNING",
                    component="detection_service",
                    message=(
                        f"Suspect flow detected from {event_record.src_ip} "
                        f"to {event_record.dst_ip} ({event_record.attack_type})."
                    ),
                    category="detection",
                )

            if self._should_record_blocking_history(result):
                blocking_record = self._build_blocking_record(
                    result=result,
                    operational_metadata=operational_metadata,
                    row_payload=row_payload,
                )
                self._append_history_item(self._recent_blocking, blocking_record)
                if blocking_record.triggered:
                    self._record_log(
                        level="WARNING",
                        component="blocking_service",
                        message=(
                            f"Blocking decision triggered for {blocking_record.src_ip} "
                            f"to {blocking_record.dst_ip} in {blocking_record.mode} mode."
                        ),
                        category="blocking",
                    )

        self._record_log(
            level="INFO",
            component="live_runtime_service",
            message=(
                f"Processed {len(results)} flow(s): "
                f"{alerts_increment} alert(s), {block_increment} block decision(s)."
            ),
            category="runtime",
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
            self._record_log_locked(
                level="ERROR",
                component="live_runtime_service",
                message=message,
                category="runtime",
            )
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

    def _reset_history_locked(self) -> None:
        self._recent_events = []
        self._recent_alerts = []
        self._recent_blocking = []
        self._recent_logs = []

    def _record_log(
        self,
        *,
        level: str,
        component: str,
        message: str,
        category: str,
        source: str = "live_runtime",
    ) -> None:
        with self._lock:
            self._record_log_locked(
                level=level,
                component=component,
                message=message,
                category=category,
                source=source,
            )

    def _record_log_locked(
        self,
        *,
        level: str,
        component: str,
        message: str,
        category: str,
        source: str = "live_runtime",
    ) -> None:
        record = LiveLogRecordResponse(
            timestamp=utc_now_iso(),
            level=level,
            component=component,
            message=message,
            category=category,
            source=source,
        )
        self._append_history_item(self._recent_logs, record)

    def _append_history_item(self, history: list[Any], item: Any) -> None:
        with self._lock:
            history.append(item)
            overflow = len(history) - self.settings.live_history_limit
            if overflow > 0:
                del history[:overflow]

    def _build_event_record(
        self,
        *,
        row_payload: dict[str, Any],
        operational_metadata: OperationalMetadata,
        result: FlowDetectionResponse,
    ) -> LiveEventRecordResponse:
        protocol = self._safe_text(
            row_payload.get("protocol") or result.blocking_decision.protocol,
            default="IP",
        )
        severity = (
            operational_metadata.severity
            or self._derive_severity(
                confidence=result.confidence,
                is_suspect=result.alert_triggered,
                triggered=result.blocking_decision.triggered,
            )
        )
        attack_type = (
            operational_metadata.scenario_family
            or operational_metadata.label_family
            or self._derive_attack_type(
                protocol=protocol,
                row_payload=row_payload,
                result=result,
            )
        )
        return LiveEventRecordResponse(
            event_id=operational_metadata.flow_id or f"evt-{uuid4()}",
            timestamp=result.timestamp_decision,
            src_ip=self._safe_text(
                operational_metadata.src_ip or row_payload.get("src_ip"),
                default="unknown",
            ),
            dst_ip=self._safe_text(
                operational_metadata.dst_ip or row_payload.get("dst_ip"),
                default="unknown",
            ),
            src_port=self._safe_int(
                row_payload.get("src_port") or result.blocking_decision.source_port
            ),
            dst_port=self._safe_int(
                row_payload.get("dst_port") or result.blocking_decision.destination_port
            ),
            protocol=protocol,
            packet_count=self._safe_int(row_payload.get("packet_count_total"), default=0)
            or 0,
            byte_count=self._safe_int(row_payload.get("byte_count_total"), default=0)
            or 0,
            duration_ms=self._safe_float(row_payload.get("duration_ms"), default=0.0)
            or 0.0,
            tcp_flags=self._build_tcp_flags(row_payload),
            entropy=None,
            prediction_label=result.predicted_label,
            raw_prediction_label=result.raw_predicted_label,
            risk_score=result.confidence,
            severity=self._safe_text(severity, default="normal") or "normal",
            attack_type=self._safe_text(attack_type, default="unclassified_flow")
            or "unclassified_flow",
            action_taken=self._derive_action_taken(result),
            status=self._derive_event_status(result),
            blocked=result.blocking_decision.triggered,
            flow_id=operational_metadata.flow_id
            or self._safe_text(row_payload.get("flow_id")),
            source="live_runtime",
        )

    def _build_alert_record(
        self,
        *,
        event_record: LiveEventRecordResponse,
        row_payload: dict[str, Any],
        result: FlowDetectionResponse,
    ) -> LiveAlertRecordResponse:
        alert_created_at = utc_now_iso()
        flow_ended_at = self._safe_text(row_payload.get("end_time"))
        flow_finalized_at = self._safe_text(row_payload.get("flow_finalized_at"))
        prediction_done_at = result.timestamp_decision
        return LiveAlertRecordResponse(
            alert_id=f"alt-{uuid4()}",
            timestamp=event_record.timestamp,
            attack_type=event_record.attack_type,
            severity=event_record.severity,
            src_ip=event_record.src_ip,
            dst_ip=event_record.dst_ip,
            description=(
                f"Suspect flow detected from {event_record.src_ip} "
                f"to {event_record.dst_ip} over {event_record.protocol}."
            ),
            recommendation=(
                "Review the source host, preserve flow evidence and keep prevention "
                "in dry_run unless the lab scenario explicitly requires enforcement."
            ),
            action_taken=self._derive_action_taken(result),
            status="escalated" if result.blocking_decision.triggered else "open",
            risk_score=result.confidence,
            flow_started_at=self._safe_text(row_payload.get("start_time")),
            flow_ended_at=flow_ended_at,
            flow_finalized_at=flow_finalized_at,
            prediction_done_at=prediction_done_at,
            alert_created_at=alert_created_at,
            latency_from_flow_end_ms=self._latency_ms(flow_ended_at, alert_created_at),
            latency_from_finalization_ms=self._latency_ms(
                flow_finalized_at,
                alert_created_at,
            ),
        )

    def _build_blocking_record(
        self,
        *,
        result: FlowDetectionResponse,
        operational_metadata: OperationalMetadata,
        row_payload: dict[str, Any],
    ) -> LiveBlockingRecordResponse:
        decision = result.blocking_decision
        return LiveBlockingRecordResponse(
            block_id=decision.block_id,
            timestamp=decision.created_at,
            src_ip=self._safe_text(
                decision.source_ip or operational_metadata.src_ip or row_payload.get("src_ip"),
                default="unknown",
            )
            or "unknown",
            dst_ip=self._safe_text(
                decision.destination_ip or operational_metadata.dst_ip or row_payload.get("dst_ip"),
                default="unknown",
            )
            or "unknown",
            src_port=decision.source_port or self._safe_int(row_payload.get("src_port")),
            dst_port=decision.destination_port or self._safe_int(row_payload.get("dst_port")),
            protocol=self._safe_text(
                decision.protocol or row_payload.get("protocol"),
                default="IP",
            )
            or "IP",
            predicted_label=result.predicted_label,
            confidence=result.confidence,
            reason=decision.reason,
            mode=decision.mode.value,
            triggered=decision.triggered,
            command_preview=decision.command_preview,
            status=self._derive_blocking_status(result),
        )

    @staticmethod
    def _should_record_blocking_history(result: FlowDetectionResponse) -> bool:
        return (
            result.raw_predicted_label == result.positive_label
            or result.alert_triggered
            or result.blocking_decision.triggered
        )

    @staticmethod
    def _derive_action_taken(result: FlowDetectionResponse) -> str:
        if result.blocking_decision.triggered:
            return f"block_{result.blocking_decision.mode.value}"
        if result.alert_triggered:
            return "alert_only"
        return "allow"

    @staticmethod
    def _derive_event_status(result: FlowDetectionResponse) -> str:
        if result.blocking_decision.triggered:
            return "blocked"
        if result.alert_triggered:
            return "open"
        return "closed"

    @staticmethod
    def _derive_blocking_status(result: FlowDetectionResponse) -> str:
        if result.blocking_decision.triggered:
            return (
                "executed"
                if result.blocking_decision.mode == BlockingMode.ENFORCE
                else "simulated"
            )
        return "alert_only"

    @staticmethod
    def _derive_severity(
        *,
        confidence: float | None,
        is_suspect: bool,
        triggered: bool,
    ) -> str:
        if not is_suspect:
            return "normal"
        resolved_confidence = float(confidence or 0.0)
        if triggered or resolved_confidence >= 0.99:
            return "critical"
        if resolved_confidence >= 0.95:
            return "high"
        if resolved_confidence >= 0.80:
            return "medium"
        return "low"

    @staticmethod
    def _derive_attack_type(
        *,
        protocol: str | None,
        row_payload: dict[str, Any],
        result: FlowDetectionResponse,
    ) -> str:
        normalized_protocol = (protocol or "ip").lower()
        if result.predicted_label != result.positive_label:
            return f"benign_{normalized_protocol}"
        syn_count = LiveRuntimeService._safe_int(row_payload.get("syn_count"), default=0) or 0
        rst_count = LiveRuntimeService._safe_int(row_payload.get("rst_count"), default=0) or 0
        if normalized_protocol == "tcp" and syn_count > 0 and rst_count > 0:
            return "syn_burst"
        if normalized_protocol == "icmp":
            return "icmp_anomaly"
        if normalized_protocol == "udp":
            return "udp_anomaly"
        return "suspect_flow"

    @staticmethod
    def _build_tcp_flags(row_payload: dict[str, Any]) -> str | None:
        flag_pairs = [
            ("SYN", "syn_count"),
            ("ACK", "ack_count"),
            ("FIN", "fin_count"),
            ("RST", "rst_count"),
            ("PSH", "psh_count"),
            ("URG", "urg_count"),
        ]
        active_flags = [
            label
            for label, key in flag_pairs
            if (LiveRuntimeService._safe_int(row_payload.get(key), default=0) or 0) > 0
        ]
        return ",".join(active_flags) or None

    @staticmethod
    def _safe_int(value: Any, default: int | None = None) -> int | None:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: Any, default: float | None = None) -> float | None:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_text(value: Any, default: str | None = None) -> str | None:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    @staticmethod
    def _latency_ms(start_iso: str | None, end_iso: str | None) -> float | None:
        if not start_iso or not end_iso:
            return None
        try:
            start_dt = datetime.fromisoformat(start_iso)
            end_dt = datetime.fromisoformat(end_iso)
        except ValueError:
            return None
        return round((end_dt - start_dt).total_seconds() * 1000.0, 3)

    @staticmethod
    def _is_timestamp_after(candidate: str | None, reference: str | None) -> bool:
        if not candidate or not reference:
            return False
        try:
            return datetime.fromisoformat(candidate) > datetime.fromisoformat(reference)
        except ValueError:
            return False
