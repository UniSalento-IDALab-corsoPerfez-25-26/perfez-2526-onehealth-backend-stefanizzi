from fastapi import FastAPI

from services.health.app.routes import (
    router,
)


app = FastAPI(
    title="OneHealthAI Health Service",
    version="1.0.0",
    description=(
        "Health domain microservice "
        "for the OneHealthAI platform."
    ),
)


@app.get("/health")
def health() -> dict:
    return {
        "service": "health-service",
        "status": "UP",
        "version": "1.0.0",
    }


app.include_router(
    router,
    prefix="/v1",
)