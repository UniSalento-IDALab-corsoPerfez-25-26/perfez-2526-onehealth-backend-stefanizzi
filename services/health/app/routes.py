from fastapi import APIRouter, Query

from services.health.app.service import (
    HealthService,
)

from services.health.app.ingestion import (
    HealthIngestionService,
)

health_ingestion_service = HealthIngestionService()

router = APIRouter()

health_service = HealthService()

@router.post("/ingestion/run")
def run_ingestion():
    return health_ingestion_service.run()


@router.get("/indicators")
def get_indicators():
    items = (
        health_service
        .get_indicators()
    )

    return {
        "items": items,
        "count": len(items),
    }


@router.get("/cases")
def get_cases(
    indicator_code: str | None = Query(
        default=None
    ),
    year: int | None = Query(
        default=None
    ),
    asl: str | None = Query(
        default=None
    ),
    sex: str | None = Query(
        default=None
    ),
    age_group: str | None = Query(
        default=None
    ),
):
    items = health_service.get_cases(
        indicator_code=indicator_code,
        year=year,
        asl=asl,
        sex=sex,
        age_group=age_group,
    )

    return {
        "items": items,
        "count": len(items),
    }


@router.get("/summary")
def get_summary():
    return (
        health_service
        .get_summary()
    )


@router.get("/quality")
def get_quality():
    return (
        health_service
        .get_quality()
    )

