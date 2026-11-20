from fastapi import FastAPI

from services.ai.app.routes import (
    router,
)


app = FastAPI(
    title="OneHealthAI AI Service",
    version="1.0.0",
    description=(
        "Explainable AI and territorial "
        "decision-support service for the "
        "OneHealthAI platform."
    ),
)


@app.get("/health")
def health() -> dict:
    return {
        "service": "ai-service",
        "status": "UP",
        "version": "1.0.0",
    }


app.include_router(
    router,
    prefix="/v1",
)