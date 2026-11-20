from fastapi import FastAPI
from services.meteorology.app.routes import router as meteorology_router
from app.api.research_routes import router as research_router

from app.api.one_health_routes import (
    router as one_health_router,
)
from app.api.routes import router as base_router


app = FastAPI(
    title="One Health Puglia DSS",
    version="0.2.0",
    description=(
        "API per l'integrazione di dati ambientali, "
        "sanitari e demografici della Regione Puglia."
    ),
)

app.include_router(base_router)
app.include_router(one_health_router)
app.include_router(research_router)
app.include_router(meteorology_router, prefix="/v1", tags=["Meteorology"])


@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "one-health-puglia-api",
        "version": "0.2.0",
    }