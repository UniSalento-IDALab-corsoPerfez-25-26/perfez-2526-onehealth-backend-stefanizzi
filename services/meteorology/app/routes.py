from fastapi import APIRouter, Query

from services.meteorology.app.service import (
    MeteorologyService,
)

from services.meteorology.app.ingestion import (
    MeteorologyIngestionService,
)

router = APIRouter()

meteorology_service = MeteorologyService()

meteorology_ingestion_service = (
    MeteorologyIngestionService()
)

@router.get("/meteorology")
def get_meteorology(
    year: int | None = Query(
        default=None
    ),
    asl: str | None = Query(
        default=None
    ),
):
    items = (
        meteorology_service
        .get_meteorology(
            year=year,
            asl=asl,
        )
    )

    return {
        "items": items,
        "count": len(items),
    }


@router.get("/summary")
def get_summary():
    return (
        meteorology_service
        .get_summary()
    )


@router.get("/quality")
def get_quality():
    return (
        meteorology_service
        .get_quality()
    )

@router.post("/ingestion/run")
def run_ingestion(
    year: int = 2023,
):
    return (
        meteorology_ingestion_service
        .run(
            year=year
        )
    )