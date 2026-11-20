import os


HEALTH_SERVICE_URL = os.getenv(
    "HEALTH_SERVICE_URL",
    "http://127.0.0.1:8002",
)

DEMOGRAPHY_SERVICE_URL = os.getenv(
    "DEMOGRAPHY_SERVICE_URL",
    "http://127.0.0.1:8003",
)

ENVIRONMENT_SERVICE_URL = os.getenv(
    "ENVIRONMENT_SERVICE_URL",
    "http://127.0.0.1:8001",
)

METEOROLOGY_SERVICE_URL = os.getenv(
    "METEOROLOGY_SERVICE_URL",
    "http://127.0.0.1:8004",
)

INTEGRATION_SERVICE_URL = os.getenv(
    "INTEGRATION_SERVICE_URL",
    "http://127.0.0.1:8005",
)

ANALYTICS_SERVICE_URL = os.getenv(
    "ANALYTICS_SERVICE_URL",
    "http://127.0.0.1:8006",
)

AI_SERVICE_URL = os.getenv(
    "AI_SERVICE_URL",
    "http://127.0.0.1:8007",
)


REQUEST_TIMEOUT_SECONDS = float(
    os.getenv(
        "ORCHESTRATOR_REQUEST_TIMEOUT_SECONDS",
        "300",
    )
)