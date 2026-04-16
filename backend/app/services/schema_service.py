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
    feature_dtypes: dict[str, str]
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

        categorical_columns = tuple(
            column for column in input_columns if column == "protocol"
        )
        numeric_columns = tuple(
            column for column in input_columns if column not in categorical_columns
        )
        feature_dtypes = self._load_feature_dtypes(
            raw_metadata=raw_metadata,
            input_columns=input_columns,
            categorical_columns=categorical_columns,
        )
        referenced_dataset_paths = {
            split: self._resolve_dataset_path(
                raw_value=raw_metadata.get(f"{split}_path"),
                fallback=self.settings.dataset_paths[split],
                metadata_dir=path.parent,
            )
            for split in ("train", "validation", "test")
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
            feature_dtypes=feature_dtypes,
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

    def _load_feature_dtypes(
        self,
        *,
        raw_metadata: dict[str, Any],
        input_columns: tuple[str, ...],
        categorical_columns: tuple[str, ...],
    ) -> dict[str, str]:
        raw_dtype_map = raw_metadata.get("runtime_feature_dtypes")
        if raw_dtype_map is None:
            self.logger.warning(
                "Metadata is missing runtime feature dtypes; defaulting numeric features to float64 for portable inference.",
                extra={
                    "context": {
                        "metadata_path": str(self.settings.metadata_path),
                    }
                },
            )
            return {
                column: "string" if column in categorical_columns else "float64"
                for column in input_columns
            }

        if not isinstance(raw_dtype_map, dict):
            raise ConfigurationError("runtime_feature_dtypes must be a JSON object.")

        missing_columns = sorted(set(input_columns) - set(raw_dtype_map))
        extra_columns = sorted(set(raw_dtype_map) - set(input_columns))
        if missing_columns or extra_columns:
            problems: list[str] = []
            if missing_columns:
                problems.append(
                    "missing: " + ", ".join(missing_columns)
                )
            if extra_columns:
                problems.append(
                    "unexpected: " + ", ".join(extra_columns)
                )
            raise ConfigurationError(
                "runtime_feature_dtypes does not match the feature contract ("
                + "; ".join(problems)
                + ")."
            )

        normalized: dict[str, str] = {}
        for column in input_columns:
            normalized[column] = self._normalize_dtype_spec(
                column=column,
                dtype_spec=str(raw_dtype_map[column]),
                categorical_columns=categorical_columns,
            )
        return normalized

    @staticmethod
    def _normalize_dtype_spec(
        *,
        column: str,
        dtype_spec: str,
        categorical_columns: tuple[str, ...],
    ) -> str:
        if column in categorical_columns:
            return "string"

        normalized = dtype_spec.strip().lower()
        if normalized.startswith("int"):
            return "int64"
        if normalized in {"str", "string", "object"}:
            raise ConfigurationError(
                f"Feature {column} is numeric in the contract but its dtype is string-like."
            )
        return "float64"

    def _resolve_dataset_path(
        self,
        *,
        raw_value: Any,
        fallback: Path,
        metadata_dir: Path,
    ) -> Path:
        if fallback.exists():
            return fallback

        if raw_value in (None, ""):
            return fallback

        candidate = Path(str(raw_value))
        if candidate.is_absolute():
            return candidate

        metadata_relative = (metadata_dir / candidate).resolve()
        if metadata_relative.exists():
            return metadata_relative

        project_relative = (self.settings.project_root / candidate).resolve()
        if project_relative.exists():
            return project_relative

        return fallback
