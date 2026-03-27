from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXTERNAL_ROOT = Path(
    r"K:\4. UQO\04. INF4523 - Réseaux d'ordinateurs\7. IPS - IA - INF4523 met a jour"
)


@dataclass(frozen=True)
class Settings:
    project_root: Path
    app_name: str
    app_version: str
    log_level: str
    blocking_mode: str
    replay_default_delay_seconds: float
    model_path: Path
    metadata_path: Path
    train_path: Path
    validation_path: Path
    test_path: Path

    @property
    def dataset_paths(self) -> dict[str, Path]:
        return {
            "train": self.train_path,
            "validation": self.validation_path,
            "test": self.test_path,
        }


def build_settings() -> Settings:
    return Settings(
        project_root=PROJECT_ROOT,
        app_name="Projet INF4523 - IPS IA Backend",
        app_version="0.1.0",
        log_level=os.getenv("IPS_LOG_LEVEL", "INFO"),
        blocking_mode=os.getenv("IPS_BLOCKING_MODE", "dry_run"),
        replay_default_delay_seconds=float(
            os.getenv("IPS_REPLAY_DEFAULT_DELAY_SECONDS", "0.0")
        ),
        model_path=Path(
            os.getenv(
                "IPS_MODEL_PATH",
                str(DEFAULT_EXTERNAL_ROOT / "models" / "random_forest_v1.joblib"),
            )
        ),
        metadata_path=Path(
            os.getenv(
                "IPS_METADATA_PATH",
                str(
                    DEFAULT_EXTERNAL_ROOT
                    / "models"
                    / "random_forest_v1_metadata.json"
                ),
            )
        ),
        train_path=Path(
            os.getenv(
                "IPS_TRAIN_PATH",
                str(
                    DEFAULT_EXTERNAL_ROOT
                    / "data"
                    / "processed"
                    / "kali_lab_v1"
                    / "05. train.parquet"
                ),
            )
        ),
        validation_path=Path(
            os.getenv(
                "IPS_VALIDATION_PATH",
                str(
                    DEFAULT_EXTERNAL_ROOT
                    / "data"
                    / "processed"
                    / "kali_lab_v1"
                    / "06. validation.parquet"
                ),
            )
        ),
        test_path=Path(
            os.getenv(
                "IPS_TEST_PATH",
                str(
                    DEFAULT_EXTERNAL_ROOT
                    / "data"
                    / "processed"
                    / "kali_lab_v1"
                    / "04. test.parquet"
                ),
            )
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return build_settings()
