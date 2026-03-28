from __future__ import annotations


class ApplicationError(Exception):
    """Base application exception exposed through FastAPI."""

    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(ApplicationError):
    status_code = 500


class DatasetError(ApplicationError):
    status_code = 500


class FeatureContractError(ApplicationError):
    status_code = 400


class ModelLoadError(ApplicationError):
    status_code = 500


class PredictionError(ApplicationError):
    status_code = 500


class BlockingError(ApplicationError):
    status_code = 500


class ReplayError(ApplicationError):
    status_code = 409


class CaptureError(ApplicationError):
    status_code = 500


class LiveRuntimeError(ApplicationError):
    status_code = 409
