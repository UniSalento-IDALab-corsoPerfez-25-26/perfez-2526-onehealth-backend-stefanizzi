from fastapi import FastAPI

from services.demography.app.routes import (
    router,
)


app = FastAPI(
    title="OneHealthAI Demography Service",
    version="1.0.0",
    description=(
        "Demography domain microservice "
        "for the OneHealthAI platform."
    ),
)


@app.get("/health")
def health() -> dict:
    return {
        "service": "demography-service",
        "status": "UP",
        "version": "1.0.0",
    }


app.include_router(
    router,
    prefix="/v1",
)