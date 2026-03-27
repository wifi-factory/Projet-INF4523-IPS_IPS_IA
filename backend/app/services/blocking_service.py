from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

from ..config import Settings
from ..core.logging import get_logger
from ..models.api_models import BlockingDecisionResponse, BlockingMode, OperationalMetadata
from ..utils.firewall_utils import build_firewall_command_preview
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
    ) -> BlockingDecisionResponse:
        mode = self._resolve_mode(blocking_mode)
        contract = self.schema_service.get_contract()
        triggered = predicted_label == contract.positive_label
        flow_features = flow_features or {}

        source_ip = operational_metadata.src_ip if operational_metadata else None
        destination_ip = operational_metadata.dst_ip if operational_metadata else None
        source_port = self._extract_int(flow_features, "src_port")
        destination_port = self._extract_int(flow_features, "dst_port")
        protocol = self._extract_text(flow_features, "protocol")

        command_preview = None
        if triggered:
            command_preview = build_firewall_command_preview(
                source_ip=source_ip,
                destination_ip=destination_ip,
                protocol=protocol,
                source_port=source_port,
                destination_port=destination_port,
            )

        reason = (
            "post-flow-classification suspect decision"
            if triggered
            else "no blocking action for non-suspect classification"
        )
        response = BlockingDecisionResponse(
            block_id=str(uuid4()),
            triggered=triggered,
            mode=mode,
            predicted_label=predicted_label,
            confidence=confidence,
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
                    "mode": response.mode.value,
                    "predicted_label": predicted_label,
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
