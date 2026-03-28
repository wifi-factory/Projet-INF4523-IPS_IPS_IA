from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

from ..config import Settings
from ..core.logging import get_logger
from ..models.api_models import BlockingDecisionResponse, BlockingMode, OperationalMetadata
from ..utils.firewall_utils import apply_firewall_command, build_firewall_command_preview
from ..utils.time_utils import utc_now_iso
from .schema_service import SchemaService


class BlockingService:
    def __init__(self, settings: Settings, schema_service: SchemaService) -> None:
        self.settings = settings
        self.schema_service = schema_service
        self.logger = get_logger(self.__class__.__name__)

    def evaluate(
        self,
        *,
        predicted_label: str,
        confidence: float | None,
        operational_metadata: OperationalMetadata | None = None,
        flow_features: Mapping[str, Any] | None = None,
        blocking_mode: BlockingMode | str | None = None,
        block_threshold_met: bool = True,
        threshold_source: str | None = None,
    ) -> BlockingDecisionResponse:
        mode = self._resolve_mode(blocking_mode)
        contract = self.schema_service.get_contract()
        is_suspect = predicted_label == contract.positive_label
        triggered = is_suspect and block_threshold_met
        flow_features = flow_features or {}

        source_ip = operational_metadata.src_ip if operational_metadata else None
        destination_ip = operational_metadata.dst_ip if operational_metadata else None
        source_port = self._extract_int(flow_features, "src_port")
        destination_port = self._extract_int(flow_features, "dst_port")
        protocol = self._extract_text(flow_features, "protocol")

        command_preview = None
        if is_suspect:
            command_preview = build_firewall_command_preview(
                source_ip=source_ip,
                destination_ip=destination_ip,
                protocol=protocol,
                source_port=source_port,
                destination_port=destination_port,
            )

        effective_mode = mode
        if not is_suspect:
            reason = "no blocking action for non-suspect classification"
        elif not block_threshold_met:
            reason = "suspect classification below block confidence threshold"
        elif mode == BlockingMode.ENFORCE:
            applied, detail = apply_firewall_command(command_preview or "")
            if applied:
                reason = "post-flow-classification suspect decision"
            else:
                effective_mode = BlockingMode.DRY_RUN
                reason = detail
        else:
            reason = "post-flow-classification suspect decision"

        response = BlockingDecisionResponse(
            block_id=str(uuid4()),
            triggered=triggered,
            mode=effective_mode,
            predicted_label=predicted_label,
            confidence=confidence,
            threshold_source=threshold_source,
            reason=reason,
            source_ip=source_ip,
            destination_ip=destination_ip,
            source_port=source_port,
            destination_port=destination_port,
            protocol=protocol,
            created_at=utc_now_iso(),
            command_preview=command_preview,
        )
        self.logger.info(
            "Blocking decision evaluated",
            extra={
                    "context": {
                        "triggered": triggered,
                        "requested_mode": mode.value,
                        "mode": response.mode.value,
                        "predicted_label": predicted_label,
                        "block_threshold_met": block_threshold_met,
                        "threshold_source": threshold_source,
                        "source_ip": source_ip,
                        "destination_ip": destination_ip,
                    }
            },
        )
        return response

    def _resolve_mode(self, value: BlockingMode | str | None) -> BlockingMode:
        if value is None:
            return BlockingMode(self.settings.blocking_mode)
        if isinstance(value, BlockingMode):
            return value
        return BlockingMode(value)

    @staticmethod
    def _extract_int(payload: Mapping[str, Any], key: str) -> int | None:
        value = payload.get(key)
        return int(value) if value is not None else None

    @staticmethod
    def _extract_text(payload: Mapping[str, Any], key: str) -> str | None:
        value = payload.get(key)
        return str(value) if value is not None else None
