from __future__ import annotations

from typing import Any

import pandas as pd

from ..config import Settings
from ..core.logging import get_logger
from ..models.api_models import (
    DatasetSchemaComparison,
    DatasetSplitSummary,
    DatasetSummaryResponse,
)
from ..utils.parquet_utils import compare_schemas, read_parquet_frame, summarize_dataframe


class DatasetService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(self.__class__.__name__)
        self._frames: dict[str, pd.DataFrame] = {}
        self._summary_cache: DatasetSummaryResponse | None = None

    def load_split(self, split: str) -> pd.DataFrame:
        if split not in self.settings.dataset_paths:
            raise KeyError(f"Unsupported split: {split}")
        if split not in self._frames:
            path = self.settings.dataset_paths[split]
            frame = read_parquet_frame(path)
            self._frames[split] = frame
            self.logger.info(
                "Dataset split loaded",
                extra={
                    "context": {
                        "split": split,
                        "path": str(path),
                        "rows": len(frame),
                        "columns": len(frame.columns),
                    }
                },
            )
        return self._frames[split]

    def get_feature_dtypes(self, columns: list[str]) -> dict[str, Any]:
        train_frame = self.load_split("train")
        return {column: train_frame.dtypes[column] for column in columns}

    def get_summary(self) -> DatasetSummaryResponse:
        if self._summary_cache is not None:
            return self._summary_cache

        frames = {split: self.load_split(split) for split in self.settings.dataset_paths}
        splits = {
            split: DatasetSplitSummary.model_validate(
                summarize_dataframe(split, self.settings.dataset_paths[split], frame)
            )
            for split, frame in frames.items()
        }
        schema_comparison = DatasetSchemaComparison.model_validate(compare_schemas(frames))
        self._summary_cache = DatasetSummaryResponse(
            splits=splits,
            schema_comparison=schema_comparison,
        )
        return self._summary_cache
