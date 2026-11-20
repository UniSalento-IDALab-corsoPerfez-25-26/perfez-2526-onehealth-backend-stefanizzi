from fastapi import FastAPI

from services.analytics.app.routes import (
    router,
)


app = FastAPI(
    title="OneHealthAI Analytics Service",
    version="1.0.0",
    description=(
        "Descriptive and statistical analytics "
        "microservice for the OneHealthAI platform."
    ),
)


@app.get("/health")
def health() -> dict:
    return {
        "service": "analytics-service",
        "status": "UP",
        "version": "1.0.0",
    }


app.include_router(
    router,
    prefix="/v1",
)