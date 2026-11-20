from fastapi import FastAPI

from services.integration.app.routes import (
    router,
)


app = FastAPI(
    title="OneHealthAI Integration Service",
    version="1.0.0",
    description=(
        "Cross-domain integration microservice "
        "for the OneHealthAI platform."
    ),
)


@app.get("/health")
def health() -> dict:
    return {
        "service": "integration-service",
        "status": "UP",
        "version": "1.0.0",
    }


app.include_router(
    router,
    prefix="/v1",
)