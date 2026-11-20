from fastapi import APIRouter, Query

from services.integration.app.service import (
    IntegrationService,
)
from services.integration.app.ingestion import (
    IntegrationIngestionService,
)

router = APIRouter()

integration_service = (
    IntegrationService()
)

integration_ingestion_service = (
    IntegrationIngestionService()
)

@router.get("/master")
def get_master(
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
    items = integration_service.get_master(
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
        integration_service
        .get_summary()
    )


@router.get("/quality")
def get_quality():
    return (
        integration_service
        .get_quality()
    )

@router.post("/ingestion/run")
def run_ingestion(
    start_year: int = 2021,
    end_year: int = 2023,
):
    return (
        integration_ingestion_service
        .run(
            start_year=start_year,
            end_year=end_year,
        )
    )