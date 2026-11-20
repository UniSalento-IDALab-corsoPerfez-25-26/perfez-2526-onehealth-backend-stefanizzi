from __future__ import annotations

from pathlib import Path

import pandas as pd

from etl.parsers.meteorology import (
    parse_meteorological_measurements,
)
from etl.validators.meteorology import (
    LOGICAL_KEY,
    validate_meteorological_measurements,
)

DST_SPRING_HOUR = 3

def _is_dst_spring_conflict(
    group: pd.DataFrame,
) -> bool:
    """
    Riconosce duplicati compatibili con il passaggio
    all'ora legale nell'ultima domenica di marzo.

    Gestisce sia dataset orari sia sub-orari.
    """

    if len(group) != 2:
        return False

    timestamps = (
        group["measurement_datetime"]
        .dropna()
        .drop_duplicates()
    )

    if len(timestamps) != 1:
        return False

    timestamp = timestamps.iloc[0]

    is_last_sunday_of_march = (
        timestamp.month == 3
        and timestamp.day >= 25
        and timestamp.weekday() == 6
    )

    is_transition_hour = (
        timestamp.hour == 3
    )

    if not (
        is_last_sunday_of_march
        and is_transition_hour
    ):
        return False

    # Il source_record_id deve essere presente,
    # ma non richiediamo più che i due ID siano consecutivi:
    # nei dataset sub-orari gli ID delle due serie duplicate
    # possono essere interlacciati.
    if "source_record_id" not in group.columns:
        return False

    source_ids = (
        pd.to_numeric(
            group["source_record_id"],
            errors="coerce",
        )
        .dropna()
        .tolist()
    )

    if len(source_ids) != 2:
        return False

    return True

def transform_meteorological_measurements(
    source_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    """
    Esegue parsing, validazione e risoluzione controllata
    dei duplicati di una singola risorsa meteorologica oraria.

    Regole applicate:
    - interrompe la trasformazione in presenza di record REJECTED;
    - elimina i duplicati perfettamente identici;
    - gestisce il conflitto noto del passaggio all'ora legale;
    - interrompe l'elaborazione per gli altri conflitti;
    - salva il risultato normalizzato in formato Parquet.
    """

    frame = parse_meteorological_measurements(
        source_path
    )

    frame = validate_meteorological_measurements(
        frame
    )

    raw_record_count = len(frame)

    # ---------------------------------------------------------
    # Record non utilizzabili
    # ---------------------------------------------------------

    rejected = frame[
        frame["quality_status"] == "REJECTED"
    ].copy()

    if not rejected.empty:
        rejected_preview_columns = [
            column
            for column in [
                "source_record_id",
                "source_station_id",
                "measurement_datetime",
                "quality_notes",
            ]
            if column in rejected.columns
        ]

        raise ValueError(
            "Trasformazione meteorologica interrotta: "
            f"trovati {len(rejected)} record REJECTED.\n"
            f"{rejected[rejected_preview_columns].head(20).to_string(index=False)}"
        )

    # ---------------------------------------------------------
    # Gestione duplicati
    # ---------------------------------------------------------

    duplicate_mask = frame.duplicated(
        subset=LOGICAL_KEY,
        keep=False,
    )

    duplicates = frame[
        duplicate_mask
    ].copy()

    rows_to_remove: list[int] = []
    unresolved_conflicts: list[tuple] = []

    identical_groups = 0
    dst_groups = 0

    comparison_columns = [
        "station_name",
        "latitude",
        "longitude",
        "temperature",
        "temperature_validation_code",
        "relative_humidity",
        "humidity_validation_code",
        "precipitation",
        "precipitation_validation_code",
        "wind_speed",
        "wind_speed_validation_code",
        "wind_direction",
        "wind_direction_validation_code",
        "solar_radiation",
        "solar_radiation_validation_code",
        "atmospheric_pressure",
        "pressure_validation_code",
    ]

    comparison_columns = [
        column
        for column in comparison_columns
        if column in frame.columns
    ]

    if not duplicates.empty:
        for key_values, group in duplicates.groupby(
            LOGICAL_KEY,
            dropna=False,
            sort=True,
        ):
            group = group.copy()

            distinct = group[
                comparison_columns
            ].drop_duplicates()

            # -------------------------------------------------
            # Duplicato perfettamente identico
            # -------------------------------------------------

            if len(distinct) == 1:
                if "source_record_id" in group.columns:
                    ordered = group.sort_values(
                        "source_record_id",
                        na_position="last",
                    )
                else:
                    ordered = group.sort_index()

                keep_index = ordered.index[0]

                rows_to_remove.extend(
                    ordered.index[1:].tolist()
                )

                frame.loc[
                    keep_index,
                    "quality_status",
                ] = "DUPLICATE_IDENTICAL"

                existing_notes = frame.loc[
                    keep_index,
                    "quality_notes",
                ]

                existing_notes = (
                    ""
                    if pd.isna(existing_notes)
                    else str(existing_notes).strip()
                )

                resolution_note = (
                    "duplicato identico risolto; "
                    "conservato il primo record"
                )

                frame.loc[
                    keep_index,
                    "quality_notes",
                ] = (
                    f"{existing_notes}; {resolution_note}"
                    if existing_notes
                    else resolution_note
                )

                identical_groups += 1
                continue

            # -------------------------------------------------
            # Conflitto dovuto al passaggio all'ora legale
            # -------------------------------------------------

            if _is_dst_spring_conflict(group):
                ordered = group.sort_values(
                    "source_record_id",
                    na_position="first",
                )

                keep_index = ordered.index[-1]

                rows_to_remove.extend(
                    ordered.index[:-1].tolist()
                )

                frame.loc[
                    keep_index,
                    "quality_status",
                ] = "DST_CONFLICT_RESOLVED"

                existing_notes = frame.loc[
                    keep_index,
                    "quality_notes",
                ]

                existing_notes = (
                    ""
                    if pd.isna(existing_notes)
                    else str(existing_notes).strip()
                )

                resolution_note = (
                    "duplicato compatibile con il passaggio "
                    "all'ora legale; conservato il record "
                    "con source_record_id maggiore"
                )

                frame.loc[
                    keep_index,
                    "quality_notes",
                ] = (
                    f"{existing_notes}; {resolution_note}"
                    if existing_notes
                    else resolution_note
                )

                dst_groups += 1
                continue

            # -------------------------------------------------
            # Conflitto non riconosciuto
            # -------------------------------------------------

            unresolved_conflicts.append(
                key_values
            )

    if unresolved_conflicts:
        preview = unresolved_conflicts[:20]

        raise ValueError(
            "Trovati duplicati meteorologici con valori "
            "conflittuali non risolvibili automaticamente. "
            f"Gruppi conflittuali: {len(unresolved_conflicts)}. "
            f"Prime chiavi: {preview}"
        )

    if rows_to_remove:
        frame = frame.drop(
            index=rows_to_remove
        ).copy()

    # ---------------------------------------------------------
    # Controllo dopo la risoluzione
    # ---------------------------------------------------------

    remaining_duplicates = frame.duplicated(
        subset=LOGICAL_KEY,
        keep=False,
    )

    if remaining_duplicates.any():
        remaining_keys = (
            frame.loc[
                remaining_duplicates,
                LOGICAL_KEY,
            ]
            .drop_duplicates()
            .head(20)
        )

        raise RuntimeError(
            "Sono ancora presenti chiavi meteorologiche "
            "duplicate dopo la risoluzione.\n"
            f"{remaining_keys.to_string(index=False)}"
        )

    # ---------------------------------------------------------
    # Ordinamento e scrittura
    # ---------------------------------------------------------

    frame = (
        frame
        .sort_values(
            [
                "source_station_id",
                "measurement_datetime",
                "source_record_id",
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame.to_parquet(
        output_path,
        index=False,
    )

    # ---------------------------------------------------------
    # Riepilogo
    # ---------------------------------------------------------

    print("=" * 70)
    print("TRASFORMAZIONE METEOROLOGICA ORARIA")
    print("=" * 70)

    print(
        "Record RAW:",
        raw_record_count,
    )

    print(
        "Record eliminati come duplicati:",
        len(rows_to_remove),
    )

    print(
        "Gruppi duplicati identici risolti:",
        identical_groups,
    )

    print(
        "Conflitti ora legale risolti:",
        dst_groups,
    )

    print(
        "Record meteorologici elaborati:",
        len(frame),
    )

    print()
    print("QUALITY STATUS")
    print(
        frame["quality_status"]
        .value_counts(dropna=False)
        .to_string()
    )

    print()
    print(
        "Prima osservazione:",
        frame["measurement_datetime"].min(),
    )

    print(
        "Ultima osservazione:",
        frame["measurement_datetime"].max(),
    )

    print(
        "Timestamp distinti:",
        frame["measurement_datetime"].nunique(),
    )

    print(
        "Stazioni distinte:",
        frame["source_station_id"].nunique(),
    )

    print(
        "Duplicati logici residui:",
        int(
            frame.duplicated(
                subset=LOGICAL_KEY,
                keep=False,
            ).sum()
        ),
    )

    print(
        "File creato:",
        output_path,
    )

    return frame