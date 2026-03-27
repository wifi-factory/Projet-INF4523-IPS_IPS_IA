from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pandas as pd

from ..core.exceptions import DatasetError


def ensure_existing_file(path: Path) -> Path:
    if not path.exists():
        raise DatasetError(f"Required file does not exist: {path}")
    if not path.is_file():
        raise DatasetError(f"Expected a file but found another path type: {path}")
    return path


def read_parquet_frame(path: Path) -> pd.DataFrame:
    ensure_existing_file(path)
    try:
        return pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - library-specific details
        raise DatasetError(f"Unable to read parquet file {path}: {exc}") from exc


def summarize_dataframe(split: str, path: Path, frame: pd.DataFrame) -> dict[str, object]:
    missing_counts = {
        column: int(count)
        for column, count in frame.isna().sum().items()
        if int(count) > 0
    }
    label_distribution = None
    if "label_binary" in frame.columns:
        label_distribution = {
            str(label): int(count)
            for label, count in frame["label_binary"].value_counts(dropna=False).items()
        }
    return {
        "split": split,
        "path": str(path),
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
        "missing_counts": missing_counts,
        "label_distribution": label_distribution,
    }


def compare_schemas(frames: Mapping[str, pd.DataFrame]) -> dict[str, object]:
    common_columns = sorted(set.intersection(*(set(frame.columns) for frame in frames.values())))
    dtype_mismatches: list[str] = []

    reference_name = "train" if "train" in frames else next(iter(frames))
    reference_frame = frames[reference_name]
    for split, frame in frames.items():
        if split == reference_name:
            continue
        for column in common_columns:
            left = str(reference_frame.dtypes[column])
            right = str(frame.dtypes[column])
            if left != right:
                dtype_mismatches.append(
                    f"{reference_name}:{column}={left} != {split}:{column}={right}"
                )

    reference_columns = list(reference_frame.columns)
    return {
        "common_columns": common_columns,
        "schema_equal_train_validation": (
            list(frames["train"].columns) == list(frames["validation"].columns)
            if {"train", "validation"}.issubset(frames)
            else False
        ),
        "schema_equal_train_test": (
            list(frames["train"].columns) == list(frames["test"].columns)
            if {"train", "test"}.issubset(frames)
            else False
        ),
        "columns_only_in_split": {
            split: sorted(set(frame.columns) - set(reference_columns))
            for split, frame in frames.items()
        },
        "dtype_mismatches": dtype_mismatches,
    }
