
# ONEHEALTHAI_DOCKER_DB_HOST_V1
import os
from urllib.parse import urlsplit, urlunsplit

for key in ("DATABASE_URL", "SQLALCHEMY_DATABASE_URL"):
    value = os.environ.get(key)
    if value:
        parts = urlsplit(value)
        if parts.hostname in ("localhost", "127.0.0.1"):
            netloc = parts.netloc.replace(
                parts.hostname + (":" + str(parts.port) if parts.port else ""),
                "host.docker.internal" + (":" + str(parts.port) if parts.port else "")
            )
            os.environ[key] = urlunsplit(
                (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
            )

from fastapi import FastAPI

from services.environment.app.routes import (
    router,
)


app = FastAPI(
    title="OneHealthAI Environment Service",
    version="1.0.0",
    description=(
        "Environmental exposure domain microservice "
        "for the OneHealthAI platform."
    ),
)


@app.get("/health")
def health() -> dict:
    return {
        "service": "environment-service",
        "status": "UP",
        "version": "1.0.0",
    }


app.include_router(
    router,
    prefix="/v1",
)

# ONEHEALTHAI_OPERATIONAL_ROUTER_FIX_V1
from fastapi import APIRouter
from services.environment.app.routes import get_operational_status

operational_router = APIRouter()
operational_router.add_api_route(
    "/operational-status",
    get_operational_status,
    methods=["GET"],
)
app.include_router(operational_router, prefix="/v1")
