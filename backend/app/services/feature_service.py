from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pandas as pd
from pandas.api.types import is_integer_dtype

from ..core.exceptions import FeatureContractError
from ..core.logging import get_logger
from .dataset_service import DatasetService
from .schema_service import SchemaService


@dataclass
class PreparedFeatures:
    frame: pd.DataFrame
    extra_features_ignored: list[str]


class FeatureService:
    def __init__(
        self,
        schema_service: SchemaService,
        dataset_service: DatasetService,
    ) -> None:
        self.schema_service = schema_service
        self.dataset_service = dataset_service
        self.logger = get_logger(self.__class__.__name__)

    def prepare_features(self, flow_features: Mapping[str, Any]) -> PreparedFeatures:
        contract = self.schema_service.get_contract()
        expected_columns = list(contract.input_columns_before_encoding)
        missing_columns = [
            column for column in expected_columns if column not in flow_features
        ]
        if missing_columns:
            raise FeatureContractError(
                "Missing required features: " + ", ".join(missing_columns)
            )

        extra_columns = sorted(set(flow_features).difference(expected_columns))
        if extra_columns:
            self.logger.warning(
                "Extra features ignored",
                extra={"context": {"extra_features": extra_columns}},
            )

        dtype_map = self.dataset_service.get_feature_dtypes(expected_columns)
        row = {
            column: self._coerce_value(column, flow_features.get(column), dtype_map[column])
            for column in expected_columns
        }
        frame = pd.DataFrame([row], columns=expected_columns)
        return PreparedFeatures(frame=frame, extra_features_ignored=extra_columns)

    def prepare_feature_frame(
        self,
        feature_rows: Sequence[Mapping[str, Any]],
    ) -> pd.DataFrame:
        if not feature_rows:
            contract = self.schema_service.get_contract()
            return pd.DataFrame(columns=list(contract.input_columns_before_encoding))

        contract = self.schema_service.get_contract()
        expected_columns = list(contract.input_columns_before_encoding)
        dtype_map = self.dataset_service.get_feature_dtypes(expected_columns)

        normalized_rows: list[dict[str, Any]] = []
        extra_columns_seen: set[str] = set()
        for feature_row in feature_rows:
            missing_columns = [
                column for column in expected_columns if column not in feature_row
            ]
            if missing_columns:
                raise FeatureContractError(
                    "Missing required features: " + ", ".join(missing_columns)
                )

            extra_columns_seen.update(
                set(feature_row).difference(expected_columns)
            )
            normalized_rows.append(
                {
                    column: self._coerce_value(
                        column,
                        feature_row.get(column),
                        dtype_map[column],
                    )
                    for column in expected_columns
                }
            )

        if extra_columns_seen:
            self.logger.warning(
                "Extra features ignored",
                extra={"context": {"extra_features": sorted(extra_columns_seen)}},
            )

        return pd.DataFrame(normalized_rows, columns=expected_columns)

    def _coerce_value(self, column: str, value: Any, dtype: Any) -> Any:
        contract = self.schema_service.get_contract()
        if value is None:
            return None
        if column in contract.categorical_columns:
            return str(value)
        try:
            if is_integer_dtype(dtype):
                return int(value)
            return float(value)
        except (TypeError, ValueError) as exc:
            raise FeatureContractError(
                f"Feature {column} could not be coerced to the expected type."
            ) from exc
