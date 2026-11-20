from pathlib import Path


SERVICE_NAME = "environment-service"
SERVICE_VERSION = "1.0.0"

DATA_ROOT = Path("data")

RAW_ROOT = (
    DATA_ROOT
    / "raw"
    / "environment"
)

STANDARDIZED_ROOT = (
    DATA_ROOT
    / "standardized"
    / "environment"
)

CURATED_ROOT = (
    DATA_ROOT
    / "curated"
    / "environment"
)

ANALYTICS_ROOT = (
    DATA_ROOT
    / "analytics"
    / "environment"
)