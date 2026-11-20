from fastapi import APIRouter, Query

from services.environment.app.service import (
    EnvironmentService,
)

from services.environment.app.ingestion import (
    EnvironmentIngestionService,
)

router = APIRouter()

environment_service = EnvironmentService()

environment_ingestion_service = (
    EnvironmentIngestionService()
)

@router.get("/exposure")
def get_exposure(
    year: int | None = Query(
        default=None
    ),
    asl: str | None = Query(
        default=None
    ),
    pollutant_code: str | None = Query(
        default=None
    ),
):
    items = environment_service.get_exposure(
        year=year,
        asl=asl,
        pollutant_code=pollutant_code,
    )

    return {
        "items": items,
        "count": len(items),
    }


@router.get("/summary")
def get_summary():
    return (
        environment_service
        .get_summary()
    )


@router.get("/quality")
def get_quality():
    return (
        environment_service
        .get_quality()
    )

@router.post("/ingestion/run")
def run_ingestion():
    return (
        environment_ingestion_service
        .run()
    )

# ONEHEALTHAI_ARPA_OPERATIONAL_STATUS_V1
@router.get("/operational-status")
def get_operational_status():
    from fastapi import HTTPException
    from sqlalchemy import func
    from app.core.database import SessionLocal
    from app.models import EnvironmentalMeasurement

    db = SessionLocal()
    try:
        count, first_date, last_date = db.query(
            func.count(EnvironmentalMeasurement.id),
            func.min(EnvironmentalMeasurement.measurement_date),
            func.max(EnvironmentalMeasurement.measurement_date),
        ).one()

        return {
            "source": "ARPA_PUGLIA_POSTGRESQL",
            "status": "READY" if count else "EMPTY",
            "record_count": int(count),
            "first_date": str(first_date) if first_date else None,
            "last_date": str(last_date) if last_date else None,
            "mode": "READ_ONLY",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database ARPA non disponibile: {type(exc).__name__}",
        )
    finally:
        db.close()


# ONEHEALTHAI_ARPA_MEASUREMENTS_V1
@router.get("/operational-measurements")
def get_operational_measurements(
    station_id: int | None = None,
    pollutant_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    from datetime import date
    from fastapi import HTTPException
    from app.core.database import SessionLocal
    from app.models import EnvironmentalMeasurement

    if not 1 <= limit <= 1000 or offset < 0:
        raise HTTPException(422, "Paginazione non valida")

    try:
        start = date.fromisoformat(date_from) if date_from else None
        end = date.fromisoformat(date_to) if date_to else None
    except ValueError:
        raise HTTPException(422, "Formato data richiesto: YYYY-MM-DD")

    if start and end and start > end:
        raise HTTPException(422, "Intervallo date non valido")

    db = SessionLocal()
    try:
        query = db.query(EnvironmentalMeasurement)

        if station_id is not None:
            query = query.filter(EnvironmentalMeasurement.station_id == station_id)
        if pollutant_id is not None:
            query = query.filter(EnvironmentalMeasurement.pollutant_id == pollutant_id)
        if start:
            query = query.filter(EnvironmentalMeasurement.measurement_date >= start)
        if end:
            query = query.filter(EnvironmentalMeasurement.measurement_date <= end)

        records = (
            query.order_by(
                EnvironmentalMeasurement.measurement_date.desc(),
                EnvironmentalMeasurement.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [
            {
                "id": r.id,
                "station_id": r.station_id,
                "pollutant_id": r.pollutant_id,
                "measurement_date": str(r.measurement_date),
                "value": r.value,
                "unit": r.unit,
                "network": r.network,
                "quality_status": r.quality_status,
                "source": r.source,
                "source_quality_index": r.source_quality_index,
                "source_quality_class": r.source_quality_class,
            }
            for r in records
        ]

        return {
            "source": "ARPA_PUGLIA_POSTGRESQL",
            "mode": "READ_ONLY",
            "count": len(items),
            "limit": limit,
            "offset": offset,
            "items": items,
        }
    finally:
        db.close()


# ONEHEALTHAI_ARPA_ENRICHED_V1
@router.get("/operational-measurements-enriched")
def get_operational_measurements_enriched(
    province: str | None = None,
    pollutant_code: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    from datetime import date
    from fastapi import HTTPException
    from sqlalchemy import text
    from app.core.database import SessionLocal

    if not 1 <= limit <= 1000 or offset < 0:
        raise HTTPException(422, "Paginazione non valida")

    try:
        start = date.fromisoformat(date_from) if date_from else None
        end = date.fromisoformat(date_to) if date_to else None
    except ValueError:
        raise HTTPException(422, "Formato data richiesto: YYYY-MM-DD")

    if start and end and start > end:
        raise HTTPException(422, "Intervallo date non valido")

    sql = """
        SELECT
            m.id,
            m.measurement_date,
            s.name AS station_name,
            s.municipality,
            s.province,
            s.latitude,
            s.longitude,
            p.code AS pollutant_code,
            p.description AS pollutant_description,
            m.value,
            m.unit,
            m.quality_status,
            m.source
        FROM environmental_measurement m
        JOIN monitoring_station s ON m.station_id = s.id
        JOIN pollutant p ON m.pollutant_id = p.id
        WHERE (CAST(:province AS TEXT) IS NULL OR LOWER(s.province) = LOWER(CAST(:province AS TEXT)))
          AND (CAST(:pollutant AS TEXT) IS NULL OR UPPER(p.code) = UPPER(CAST(:pollutant AS TEXT)))
          AND (CAST(:start AS DATE) IS NULL OR m.measurement_date >= CAST(:start AS DATE))
          AND (CAST(:end AS DATE) IS NULL OR m.measurement_date <= CAST(:end AS DATE))
        ORDER BY m.measurement_date DESC, m.id DESC
        LIMIT :limit OFFSET :offset
    """

    params = {
        "province": province,
        "pollutant": pollutant_code,
        "start": start,
        "end": end,
        "limit": limit,
        "offset": offset,
    }

    db = SessionLocal()
    try:
        rows = db.execute(text(sql), params).mappings().all()
        items = []
        for row in rows:
            item = dict(row)
            if item["measurement_date"] is not None:
                item["measurement_date"] = str(item["measurement_date"])
            items.append(item)

        return {
            "source": "ARPA_PUGLIA_POSTGRESQL",
            "mode": "READ_ONLY",
            "count": len(items),
            "limit": limit,
            "offset": offset,
            "items": items,
        }
    finally:
        db.close()
