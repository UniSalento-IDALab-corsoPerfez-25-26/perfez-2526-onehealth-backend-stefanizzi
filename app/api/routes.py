from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import (
    DataQualityIssue,
    EnvironmentalMeasurement,
    IngestionRun,
    MonitoringStation,
    Pollutant,
)


router = APIRouter()


@router.get("/measurements/latest")
def latest_measurements(
    province: str | None = None,
    pollutant: str | None = None,
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
):
    with SessionLocal() as session:
        latest_date = session.scalar(
            select(
                func.max(
                    EnvironmentalMeasurement.measurement_date
                )
            )
        )

        if latest_date is None:
            return {
                "date": None,
                "count": 0,
                "measurements": [],
            }

        query = (
            select(
                EnvironmentalMeasurement.measurement_date,
                MonitoringStation.name.label("station"),
                MonitoringStation.municipality,
                MonitoringStation.province,
                Pollutant.code.label("pollutant"),
                EnvironmentalMeasurement.value,
                EnvironmentalMeasurement.unit,
                EnvironmentalMeasurement.quality_status,
            )
            .join(
                MonitoringStation,
                MonitoringStation.id
                == EnvironmentalMeasurement.station_id,
            )
            .join(
                Pollutant,
                Pollutant.id
                == EnvironmentalMeasurement.pollutant_id,
            )
            .where(
                EnvironmentalMeasurement.measurement_date
                == latest_date
            )
        )

        if province:
            query = query.where(
                func.lower(MonitoringStation.province)
                == province.lower()
            )

        if pollutant:
            query = query.where(
                func.upper(Pollutant.code)
                == pollutant.upper()
            )

        query = query.limit(limit)

        rows = session.execute(query).all()

        measurements = [
            {
                "date": row.measurement_date,
                "station": row.station,
                "municipality": row.municipality,
                "province": row.province,
                "pollutant": row.pollutant,
                "value": row.value,
                "unit": row.unit,
                "quality_status": row.quality_status,
            }
            for row in rows
        ]

        return {
            "date": latest_date,
            "count": len(measurements),
            "measurements": measurements,
        }


@router.get("/measurements")
def measurements(
    province: str | None = None,
    pollutant: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(
        default=500,
        ge=1,
        le=5000,
    ),
):
    with SessionLocal() as session:
        query = (
            select(
                EnvironmentalMeasurement.measurement_date,
                MonitoringStation.source_station_id,
                MonitoringStation.name.label("station"),
                MonitoringStation.municipality,
                MonitoringStation.province,
                Pollutant.code.label("pollutant"),
                EnvironmentalMeasurement.value,
                EnvironmentalMeasurement.unit,
                EnvironmentalMeasurement.source_limit,
                EnvironmentalMeasurement.source_quality_index,
                EnvironmentalMeasurement.source_quality_class,
                EnvironmentalMeasurement.quality_status,
            )
            .join(
                MonitoringStation,
                MonitoringStation.id
                == EnvironmentalMeasurement.station_id,
            )
            .join(
                Pollutant,
                Pollutant.id
                == EnvironmentalMeasurement.pollutant_id,
            )
        )

        if province:
            query = query.where(
                func.lower(MonitoringStation.province)
                == province.lower()
            )

        if pollutant:
            query = query.where(
                func.upper(Pollutant.code)
                == pollutant.upper()
            )

        if start_date:
            query = query.where(
                EnvironmentalMeasurement.measurement_date
                >= start_date
            )

        if end_date:
            query = query.where(
                EnvironmentalMeasurement.measurement_date
                <= end_date
            )

        query = (
            query
            .order_by(
                EnvironmentalMeasurement.measurement_date.desc(),
                MonitoringStation.name,
                Pollutant.code,
            )
            .limit(limit)
        )

        rows = session.execute(query).all()

        return {
            "count": len(rows),
            "measurements": [
                {
                    "date": row.measurement_date,
                    "station_id": row.source_station_id,
                    "station": row.station,
                    "municipality": row.municipality,
                    "province": row.province,
                    "pollutant": row.pollutant,
                    "value": row.value,
                    "unit": row.unit,
                    "source_limit": row.source_limit,
                    "source_quality_index":
                        row.source_quality_index,
                    "source_quality_class":
                        row.source_quality_class,
                    "quality_status":
                        row.quality_status,
                }
                for row in rows
            ],
        }


@router.get("/quality/summary")
def quality_summary():
    with SessionLocal() as session:
        rows = session.execute(
            select(
                DataQualityIssue.issue_type,
                DataQualityIssue.severity,
                func.count(DataQualityIssue.id).label("total"),
            )
            .group_by(
                DataQualityIssue.issue_type,
                DataQualityIssue.severity,
            )
            .order_by(
                DataQualityIssue.issue_type
            )
        ).all()

        return {
            "issues": [
                {
                    "issue_type": row.issue_type,
                    "severity": row.severity,
                    "count": row.total,
                }
                for row in rows
            ]
        }


@router.get("/ingestion/latest")
def latest_ingestion():
    with SessionLocal() as session:
        run = session.scalar(
            select(IngestionRun)
            .order_by(
                IngestionRun.id.desc()
            )
            .limit(1)
        )

        if run is None:
            return {
                "status": "no_ingestion_runs"
            }

        return {
            "id": run.id,
            "source": run.source,
            "mode": run.mode,
            "dataset_type": run.dataset_type,
            "status": run.status,
            "file_path": run.file_path,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "input_records": run.input_records,
            "inserted_records": run.inserted_records,
            "updated_records": run.updated_records,
            "skipped_records": run.skipped_records,
            "warning_records": run.warning_records,
            "duplicate_records": run.duplicate_records,
            "error_message": run.error_message,
        }

@router.get("/stations")
def stations(
    province: str | None = None,
    network: str | None = None,
):
    with SessionLocal() as session:
        query = select(
            MonitoringStation.source_station_id,
            MonitoringStation.name,
            MonitoringStation.municipality,
            MonitoringStation.province,
            MonitoringStation.network,
            MonitoringStation.longitude,
            MonitoringStation.latitude,
        )

        if province:
            query = query.where(
                func.lower(MonitoringStation.province)
                == province.lower()
            )

        if network:
            query = query.where(
                func.upper(MonitoringStation.network)
                == network.upper()
            )

        query = query.order_by(
            MonitoringStation.province,
            MonitoringStation.name,
        )

        rows = session.execute(query).all()

        return {
            "count": len(rows),
            "stations": [
                {
                    "station_id": row.source_station_id,
                    "name": row.name,
                    "municipality": row.municipality,
                    "province": row.province,
                    "network": row.network,
                    "longitude": row.longitude,
                    "latitude": row.latitude,
                }
                for row in rows
            ],
        }

@router.get("/stations/geojson")
def stations_geojson(
    province: str | None = None,
    network: str | None = None,
):
    with SessionLocal() as session:
        query = select(
            MonitoringStation.source_station_id,
            MonitoringStation.name,
            MonitoringStation.municipality,
            MonitoringStation.province,
            MonitoringStation.network,
            MonitoringStation.longitude,
            MonitoringStation.latitude,
        ).where(
            MonitoringStation.longitude.is_not(None),
            MonitoringStation.latitude.is_not(None),
        )

        if province:
            query = query.where(
                func.lower(MonitoringStation.province)
                == province.lower()
            )

        if network:
            query = query.where(
                func.upper(MonitoringStation.network)
                == network.upper()
            )

        rows = session.execute(query).all()

        features = []

        for row in rows:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [
                            row.longitude,
                            row.latitude,
                        ],
                    },
                    "properties": {
                        "station_id":
                            row.source_station_id,
                        "name": row.name,
                        "municipality":
                            row.municipality,
                        "province": row.province,
                        "network": row.network,
                    },
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
        }

@router.get("/measurements/timeseries")
def measurements_timeseries(
    province: str | None = None,
    pollutant: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    with SessionLocal() as session:
        query = (
            select(
                EnvironmentalMeasurement.measurement_date,
                MonitoringStation.province,
                Pollutant.code.label("pollutant"),
                func.avg(
                    EnvironmentalMeasurement.value
                ).label("mean_value"),
                func.min(
                    EnvironmentalMeasurement.value
                ).label("min_value"),
                func.max(
                    EnvironmentalMeasurement.value
                ).label("max_value"),
                func.count(
                    EnvironmentalMeasurement.value
                ).label("valid_values"),
            )
            .join(
                MonitoringStation,
                MonitoringStation.id
                == EnvironmentalMeasurement.station_id,
            )
            .join(
                Pollutant,
                Pollutant.id
                == EnvironmentalMeasurement.pollutant_id,
            )
            .where(
                EnvironmentalMeasurement.value.is_not(None)
            )
        )

        if province:
            query = query.where(
                func.lower(MonitoringStation.province)
                == province.lower()
            )

        if pollutant:
            query = query.where(
                func.upper(Pollutant.code)
                == pollutant.upper()
            )

        if start_date:
            query = query.where(
                EnvironmentalMeasurement.measurement_date
                >= start_date
            )

        if end_date:
            query = query.where(
                EnvironmentalMeasurement.measurement_date
                <= end_date
            )

        query = (
            query
            .group_by(
                EnvironmentalMeasurement.measurement_date,
                MonitoringStation.province,
                Pollutant.code,
            )
            .order_by(
                EnvironmentalMeasurement.measurement_date
            )
        )

        rows = session.execute(query).all()

        return {
            "count": len(rows),
            "series": [
                {
                    "date": row.measurement_date,
                    "province": row.province,
                    "pollutant": row.pollutant,
                    "mean_value": float(row.mean_value)
                    if row.mean_value is not None
                    else None,
                    "min_value": float(row.min_value)
                    if row.min_value is not None
                    else None,
                    "max_value": float(row.max_value)
                    if row.max_value is not None
                    else None,
                    "valid_values": row.valid_values,
                }
                for row in rows
            ],
        }