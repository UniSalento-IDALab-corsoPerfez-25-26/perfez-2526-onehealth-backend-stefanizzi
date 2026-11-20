from pathlib import Path

import pandas as pd
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import (
    EnvironmentalMeasurement,
    MonitoringStation,
    Pollutant,
)

from etl.audit import (
    complete_ingestion_run,
    fail_ingestion_run,
    start_ingestion_run,
)

MEASUREMENT_KEY_COLUMNS = [
    "measurement_date",
    "source_station_id",
    "pollutant_code",
    "network",
]


def _none_if_nan(value):
    return None if pd.isna(value) else value


def load_stations(path: Path) -> None:
    frame = pd.read_parquet(path)

    with SessionLocal() as session:
        count = 0

        for _, row in frame.iterrows():
            source_id = str(
                row["source_station_id"]
            ).strip()

            station = session.scalar(
                select(MonitoringStation).where(
                    MonitoringStation.source_station_id
                    == source_id
                )
            )

            if station is None:
                station = MonitoringStation(
                    source_station_id=source_id,
                    name=str(row["name"]),
                )
                session.add(station)

            longitude = _none_if_nan(
                row.get("longitude")
            )
            latitude = _none_if_nan(
                row.get("latitude")
            )

            geometry = None

            if (
                longitude is not None
                and latitude is not None
            ):
                geometry = from_shape(
                    Point(
                        float(longitude),
                        float(latitude),
                    ),
                    srid=4326,
                )

            station.name = str(row["name"])

            station.municipality = _none_if_nan(
                row.get("municipality")
            )

            station.province = _none_if_nan(
                row.get("province")
            )

            station.network = _none_if_nan(
                row.get("network")
            )

            station.network_interest = _none_if_nan(
                row.get("network_interest")
            )

            station.address = _none_if_nan(
                row.get("address")
            )

            station.longitude = longitude
            station.latitude = latitude
            station.geometry = geometry
            station.source = "ARPAP"

            count += 1

        session.commit()

    print(
        f"Stazioni caricate/aggiornate: {count}"
    )


def load_pollutants(path: Path) -> None:
    frame = pd.read_parquet(path)

    with SessionLocal() as session:
        count = 0

        for _, row in frame.iterrows():
            source_id = str(
                row["source_pollutant_id"]
            ).strip()

            pollutant = session.scalar(
                select(Pollutant).where(
                    Pollutant.source_pollutant_id
                    == source_id
                )
            )

            if pollutant is None:
                pollutant = Pollutant(
                    source_pollutant_id=source_id,
                    code=str(
                        row["code"]
                    ).strip().upper(),
                )
                session.add(pollutant)

            pollutant.code = (
                str(row["code"])
                .strip()
                .upper()
            )

            pollutant.description = _none_if_nan(
                row.get("description")
            )

            pollutant.measurement_period = (
                _none_if_nan(
                    row.get("measurement_period")
                )
            )

            pollutant.unit = _none_if_nan(
                row.get("unit")
            )

            pollutant.source_limit = _none_if_nan(
                row.get("source_limit")
            )

            pollutant.alert_threshold = (
                _none_if_nan(
                    row.get("alert_threshold")
                )
            )

            pollutant.eionet_uri = _none_if_nan(
                row.get("eionet_uri")
            )

            pollutant.source = "ARPAP"

            count += 1

        session.commit()

    print(
        f"Inquinanti caricati/aggiornati: {count}"
    )


def load_measurements(path: Path) -> None:
    frame = pd.read_parquet(path).copy()

    input_count = len(frame)

    # -----------------------------------------------------
    # Conteggi qualità iniziali
    # -----------------------------------------------------

    warning_count = 0
    duplicate_count = 0

    if "quality_status" in frame.columns:
        warning_count = int(
            (
                frame["quality_status"]
                == "VALID_WITH_WARNING"
            ).sum()
        )

        duplicate_count = int(
            (
                frame["quality_status"]
                == "DUPLICATE_IDENTICAL"
            ).sum()
        )

    # -----------------------------------------------------
    # Normalizzazione delle chiavi
    # -----------------------------------------------------

    frame["source_station_id"] = (
        frame["source_station_id"]
        .astype("string")
        .str.strip()
    )

    frame["pollutant_code"] = (
        frame["pollutant_code"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    frame["network"] = (
        frame["network"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    frame["measurement_date"] = pd.to_datetime(
        frame["measurement_date"],
        errors="coerce",
    )

    # -----------------------------------------------------
    # Verifica duplicati conflittuali
    # -----------------------------------------------------

    if "quality_status" in frame.columns:
        conflicts = frame[
            frame["quality_status"]
            == "DUPLICATE_CONFLICT"
        ]

        if not conflicts.empty:
            raise ValueError(
                "Caricamento interrotto: "
                f"trovati {len(conflicts)} record "
                "DUPLICATE_CONFLICT."
            )

    # -----------------------------------------------------
    # Statistiche sui duplicati
    # -----------------------------------------------------

    duplicate_mask = frame.duplicated(
        subset=MEASUREMENT_KEY_COLUMNS,
        keep=False,
    )

    duplicated_rows = frame.loc[
        duplicate_mask
    ]

    duplicated_rows_count = len(
        duplicated_rows
    )

    duplicated_groups_count = (
        duplicated_rows.groupby(
            MEASUREMENT_KEY_COLUMNS,
            dropna=False,
        ).ngroups
        if not duplicated_rows.empty
        else 0
    )

    # -----------------------------------------------------
    # Deduplicazione per il database operativo
    # -----------------------------------------------------

    frame = frame.drop_duplicates(
        subset=MEASUREMENT_KEY_COLUMNS,
        keep="first",
    ).copy()

    unique_count = len(frame)

    # -----------------------------------------------------
    # Determinazione modalità ingestion
    # -----------------------------------------------------

    mode = (
        "DAILY"
        if "daily" in path.name.lower()
        else "BACKFILL"
    )

    # -----------------------------------------------------
    # Apertura sessione
    # -----------------------------------------------------

    with SessionLocal() as session:
        run = start_ingestion_run(
            session,
            mode=mode,
            dataset_type="ENVIRONMENTAL_MEASUREMENT",
            file_path=str(path),
        )

        inserted = 0
        updated = 0
        skipped = 0

        try:
            # -------------------------------------------------
            # Cache FK stazioni
            # -------------------------------------------------

            stations = {
                str(
                    station.source_station_id
                ).strip(): station.id
                for station in session.scalars(
                    select(MonitoringStation)
                ).all()
            }

            # -------------------------------------------------
            # Cache FK inquinanti
            # -------------------------------------------------

            pollutants = {
                pollutant.code.strip().upper():
                pollutant.id
                for pollutant in session.scalars(
                    select(Pollutant)
                ).all()
            }

            # -------------------------------------------------
            # Caricamento record
            # -------------------------------------------------

            for _, row in frame.iterrows():
                station_key = str(
                    row["source_station_id"]
                ).strip()

                pollutant_key = str(
                    row["pollutant_code"]
                ).strip().upper()

                station_id = stations.get(
                    station_key
                )

                pollutant_id = pollutants.get(
                    pollutant_key
                )

                # ---------------------------------------------
                # Foreign key non risolta
                # ---------------------------------------------

                if (
                    station_id is None
                    or pollutant_id is None
                ):
                    skipped += 1
                    continue

                # ---------------------------------------------
                # Data non valida
                # ---------------------------------------------

                if pd.isna(
                    row["measurement_date"]
                ):
                    skipped += 1
                    continue

                measurement_date = pd.Timestamp(
                    row["measurement_date"]
                ).date()

                network = str(
                    row["network"]
                ).strip().upper()

                # ---------------------------------------------
                # Ricerca record esistente
                # ---------------------------------------------

                measurement = session.scalar(
                    select(
                        EnvironmentalMeasurement
                    ).where(
                        EnvironmentalMeasurement.station_id
                        == station_id,

                        EnvironmentalMeasurement.pollutant_id
                        == pollutant_id,

                        EnvironmentalMeasurement.measurement_date
                        == measurement_date,

                        EnvironmentalMeasurement.network
                        == network,
                    )
                )

                # ---------------------------------------------
                # INSERT
                # ---------------------------------------------

                if measurement is None:
                    measurement = (
                        EnvironmentalMeasurement(
                            station_id=station_id,
                            pollutant_id=pollutant_id,
                            measurement_date=measurement_date,
                            network=network,
                        )
                    )

                    session.add(measurement)
                    session.flush()

                    inserted += 1

                # ---------------------------------------------
                # UPDATE
                # ---------------------------------------------

                else:
                    updated += 1

                # ---------------------------------------------
                # Attributi misura
                # ---------------------------------------------

                measurement.value = (
                    _none_if_nan(
                        row.get("value")
                    )
                )

                measurement.unit = (
                    _none_if_nan(
                        row.get("unit")
                    )
                )

                measurement.source_limit = (
                    _none_if_nan(
                        row.get("source_limit")
                    )
                )

                measurement.source_exceedances_ytd = (
                    _none_if_nan(
                        row.get(
                            "source_exceedances_ytd"
                        )
                    )
                )

                measurement.source_quality_index = (
                    _none_if_nan(
                        row.get(
                            "source_quality_index"
                        )
                    )
                )

                measurement.source_quality_class = (
                    _none_if_nan(
                        row.get(
                            "source_quality_class"
                        )
                    )
                )

                measurement.quality_status = (
                    _none_if_nan(
                        row.get(
                            "quality_status"
                        )
                    )
                )

                measurement.source = "ARPAP"

            # -------------------------------------------------
            # Salvataggio misure
            # -------------------------------------------------

            session.commit()

            # -------------------------------------------------
            # Aggiornamento audit
            # -------------------------------------------------

            complete_ingestion_run(
                session,
                run,
                input_records=input_count,
                inserted_records=inserted,
                updated_records=updated,
                skipped_records=skipped,
                warning_records=warning_count,
                duplicate_records=duplicate_count,
            )

        except Exception as exc:
            session.rollback()

            fail_ingestion_run(
                session,
                run,
                exc,
            )

            raise

    # -----------------------------------------------------
    # Report console
    # -----------------------------------------------------

    print(
        f"Record input: {input_count}"
    )

    print(
        "Gruppi duplicati rilevati: "
        f"{duplicated_groups_count}"
    )

    print(
        "Righe appartenenti a duplicati: "
        f"{duplicated_rows_count}"
    )

    print(
        "Record univoci elaborati: "
        f"{unique_count}"
    )

    print(
        f"Misure inserite: {inserted}"
    )

    print(
        f"Misure aggiornate: {updated}"
    )

    print(
        f"Misure saltate: {skipped}"
    )

    print(
        f"Warning rilevati: {warning_count}"
    )

    print(
        f"Duplicati identici rilevati: {duplicate_count}"
    )