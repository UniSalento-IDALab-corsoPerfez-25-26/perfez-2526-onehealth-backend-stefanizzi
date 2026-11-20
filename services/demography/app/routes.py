from fastapi import APIRouter, Query

from services.demography.app.service import (
    DemographyService,
)

from services.demography.app.ingestion import (
    DemographyIngestionService,
)

router = APIRouter()

demography_service = DemographyService()

demography_ingestion_service = (
    DemographyIngestionService()
)

@router.get("/population")
def get_population(
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
    items = demography_service.get_population(
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
        demography_service
        .get_summary()
    )


@router.get("/quality")
def get_quality():
    return (
        demography_service
        .get_quality()
    )

@router.post("/ingestion/run")
def run_ingestion():
    return (
        demography_ingestion_service
        .run()
    )