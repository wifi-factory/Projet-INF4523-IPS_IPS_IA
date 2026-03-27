from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import Settings
from ..core.exceptions import ConfigurationError
from ..core.logging import get_logger


@dataclass(frozen=True)
class FeatureContract:
    metadata_path: Path
    model_type: str
    target_column: str
    positive_label: str
    selected_candidate: dict[str, Any]
    excluded_columns: tuple[str, ...]
    input_columns_before_encoding: tuple[str, ...]
    categorical_columns: tuple[str, ...]
    numeric_columns: tuple[str, ...]
    referenced_dataset_paths: dict[str, Path]

    @property
    def feature_count(self) -> int:
        return len(self.input_columns_before_encoding)


class SchemaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(self.__class__.__name__)
        self._contract: FeatureContract | None = None

    def get_contract(self) -> FeatureContract:
        if self._contract is None:
            self._contract = self._load_contract()
        return self._contract

    def get_status(self) -> str:
        return "loaded" if self._contract is not None else "not_loaded"

    def _load_contract(self) -> FeatureContract:
        path = self.settings.metadata_path
        if not path.exists():
            raise ConfigurationError(f"Metadata file does not exist: {path}")

        try:
            raw_metadata = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - library-specific details
            raise ConfigurationError(f"Unable to load metadata JSON {path}: {exc}") from exc

        required_keys = {
            "model_type",
            "target_column",
            "positive_label",
            "selected_candidate",
            "excluded_columns",
            "input_columns_before_encoding",
        }
        missing_keys = sorted(required_keys - set(raw_metadata))
        if missing_keys:
            raise ConfigurationError(
                f"Metadata file is missing required keys: {', '.join(missing_keys)}"
            )

        input_columns = tuple(raw_metadata["input_columns_before_encoding"])
        if len(set(input_columns)) != len(input_columns):
            raise ConfigurationError("Metadata contains duplicate input columns.")

        excluded_columns = tuple(raw_metadata["excluded_columns"])
        overlap = sorted(set(input_columns).intersection(excluded_columns))
        if overlap:
            raise ConfigurationError(
                "Input columns overlap with excluded columns: " + ", ".join(overlap)
            )

        target_column = str(raw_metadata["target_column"])
        if target_column in input_columns:
            raise ConfigurationError(
                "Target column must not be part of the model input contract."
            )

        categorical_columns = tuple(column for column in input_columns if column == "protocol")
        numeric_columns = tuple(column for column in input_columns if column not in categorical_columns)

        referenced_dataset_paths = {
            "train": Path(raw_metadata.get("train_path", self.settings.train_path)),
            "validation": Path(
                raw_metadata.get("validation_path", self.settings.validation_path)
            ),
            "test": Path(raw_metadata.get("test_path", self.settings.test_path)),
        }

        contract = FeatureContract(
            metadata_path=path,
            model_type=str(raw_metadata["model_type"]),
            target_column=target_column,
            positive_label=str(raw_metadata["positive_label"]),
            selected_candidate=dict(raw_metadata["selected_candidate"]),
            excluded_columns=excluded_columns,
            input_columns_before_encoding=input_columns,
            categorical_columns=categorical_columns,
            numeric_columns=numeric_columns,
            referenced_dataset_paths=referenced_dataset_paths,
        )
        self.logger.info(
            "Feature contract loaded",
            extra={
                "context": {
                    "metadata_path": str(path),
                    "feature_count": contract.feature_count,
                    "target_column": contract.target_column,
                    "positive_label": contract.positive_label,
                }
            },
        )
        return contract
