from fastapi import FastAPI

from services.orchestrator.app.routes import (
    router,
)


app = FastAPI(
    title=(
        "OneHealthAI Orchestrator Service"
    ),
    version="1.0.0",
    description=(
        "Application-level workflow "
        "orchestrator for the "
        "OneHealthAI platform."
    ),
)


@app.get("/health")
def health() -> dict:
    return {
        "service":
            "orchestrator-service",
        "status":
            "UP",
        "version":
            "1.0.0",
    }


app.include_router(
    router,
    prefix="/v1",
)