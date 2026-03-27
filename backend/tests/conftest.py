from __future__ import annotations

import pytest

from backend.app.config import get_settings
from backend.app.services.container import build_service_container


@pytest.fixture(scope="session")
def settings():
    get_settings.cache_clear()
    settings = get_settings()
    required_paths = [
        settings.metadata_path,
        settings.model_path,
        settings.train_path,
        settings.validation_path,
        settings.test_path,
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        pytest.skip(f"Required external artifacts are missing: {missing}")
    return settings


@pytest.fixture(scope="session")
def services(settings):
    container = build_service_container(settings)
    container.schema_service.get_contract()
    container.model_service.ensure_model_loaded()
    return container


@pytest.fixture(scope="session")
def validation_frame(services):
    return services.dataset_service.load_split("validation")


@pytest.fixture(scope="session")
def sample_validation_row(validation_frame):
    return validation_frame.iloc[0]


@pytest.fixture(scope="session")
def sample_suspect_row(validation_frame):
    suspect_rows = validation_frame[validation_frame["label_binary"] == "suspect"]
    return suspect_rows.iloc[0]
