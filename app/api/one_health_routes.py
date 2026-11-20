from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.one_health import (
    DatasetNotAvailableError,
    get_environmental_exposure,
    get_one_health_data,
    get_one_health_summary,
    get_prevalence_data,
    get_quality_report,
    get_dataset_manifest,
)


router = APIRouter(
    prefix="/one-health",
    tags=["One Health"],
)


@router.get("/summary")
def one_health_summary():
    try:
        return get_one_health_summary()

    except DatasetNotAvailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/data")
def one_health_data(
    start_year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
    ),
    end_year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
    ),
    asl: str | None = None,
    indicator: str | None = None,
    sex: str | None = None,
    age_group: str | None = None,
    limit: int = Query(
        default=1000,
        ge=1,
        le=10000,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):
    if (
        start_year is not None
        and end_year is not None
        and start_year > end_year
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "start_year non può essere "
                "maggiore di end_year."
            ),
        )

    try:
        return get_one_health_data(
            start_year=start_year,
            end_year=end_year,
            asl=asl,
            indicator=indicator,
            sex=sex,
            age_group=age_group,
            limit=limit,
            offset=offset,
        )

    except DatasetNotAvailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/prevalence")
def prevalence_data(
    start_year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
    ),
    end_year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
    ),
    asl: str | None = None,
    indicator: str | None = None,
    sex: str | None = None,
    age_group: str | None = None,
    limit: int = Query(
        default=1000,
        ge=1,
        le=10000,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):
    try:
        return get_prevalence_data(
            start_year=start_year,
            end_year=end_year,
            asl=asl,
            indicator=indicator,
            sex=sex,
            age_group=age_group,
            limit=limit,
            offset=offset,
        )

    except DatasetNotAvailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get("/environment")
def environmental_exposure(
    start_year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
    ),
    end_year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
    ),
    asl: str | None = None,
    pollutant: str | None = None,
    limit: int = Query(
        default=1000,
        ge=1,
        le=10000,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):
    try:
        return get_environmental_exposure(
            start_year=start_year,
            end_year=end_year,
            asl=asl,
            pollutant=pollutant,
            limit=limit,
            offset=offset,
        )

    except DatasetNotAvailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

@router.get("/quality-report")
def quality_report():
    try:
        return get_quality_report()

    except DatasetNotAvailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

@router.get("/manifest")
def dataset_manifest():
    try:
        return get_dataset_manifest()

    except DatasetNotAvailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc