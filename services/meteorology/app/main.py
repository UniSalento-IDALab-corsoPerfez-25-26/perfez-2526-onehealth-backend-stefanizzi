from fastapi import FastAPI

from services.meteorology.app.routes import (
    router,
)


app = FastAPI(
    title="OneHealthAI Meteorology Service",
    version="1.0.0",
    description=(
        "Meteorology domain microservice "
        "for the OneHealthAI platform."
    ),
)


@app.get("/health")
def health() -> dict:
    return {
        "service": "meteorology-service",
        "status": "UP",
        "version": "1.0.0",
    }


app.include_router(
    router,
    prefix="/v1",
)