from __future__ import annotations

from pathlib import Path

import pandas as pd
from etl.release_guard import assert_legacy_output_writable


def build_one_health_master(
    *,
    one_health_path: Path,
    meteorology_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    """
    Integra il dataset One Health ambiente-salute-demografia
    con gli indicatori meteorologici disponibili.

    Il meteo è opzionale:
    - nessuna imputazione viene effettuata;
    - anni senza meteo rimangono esplicitamente senza meteo;
    - ASL senza copertura meteorologica rimangono senza meteo;
    - la qualità della copertura viene propagata nel master.
    """

    # ---------------------------------------------------------
    # Controlli iniziali
    # ---------------------------------------------------------

    assert_legacy_output_writable(output_path)
    if not one_health_path.exists():
        raise FileNotFoundError(
            "Dataset One Health non trovato: "
            f"{one_health_path}"
        )

    if not meteorology_path.exists():
        raise FileNotFoundError(
            "Dataset meteorologico non trovato: "
            f"{meteorology_path}"
        )

    one_health = pd.read_parquet(
        one_health_path
    )

    meteorology = pd.read_parquet(
        meteorology_path
    )

    if one_health.empty:
        raise ValueError(
            "Il dataset One Health è vuoto."
        )

    if meteorology.empty:
        raise ValueError(
            "Il dataset meteorologico è vuoto."
        )

    # ---------------------------------------------------------
    # Verifica schema One Health
    # ---------------------------------------------------------

    required_one_health = {
        "indicator_code",
        "year",
        "asl",
        "sex",
        "age_group",
        "cases",
        "population",
        "prevalence_per_1000",
    }

    missing_one_health = (
        required_one_health
        - set(one_health.columns)
    )

    if missing_one_health:
        raise ValueError(
            "Colonne mancanti nel dataset One Health: "
            f"{sorted(missing_one_health)}"
        )

    # ---------------------------------------------------------
    # Verifica schema meteorologico
    # ---------------------------------------------------------

    required_meteorology = {
        "year",
        "asl",
        "meteo_days_available",
        "meteo_expected_days",
        "meteo_year_coverage_percent",
        "meteo_quality_status",
        "meteo_available_variables",
    }

    missing_meteorology = (
        required_meteorology
        - set(meteorology.columns)
    )

    if missing_meteorology:
        raise ValueError(
            "Colonne mancanti nel dataset meteorologico: "
            f"{sorted(missing_meteorology)}"
        )

    # ---------------------------------------------------------
    # Normalizzazione chiavi
    # ---------------------------------------------------------

    one_health["year"] = pd.to_numeric(
        one_health["year"],
        errors="coerce",
    ).astype("Int64")

    meteorology["year"] = pd.to_numeric(
        meteorology["year"],
        errors="coerce",
    ).astype("Int64")

    one_health["asl"] = (
        one_health["asl"]
        .astype("string")
        .str.strip()
    )

    meteorology["asl"] = (
        meteorology["asl"]
        .astype("string")
        .str.strip()
    )

    # ---------------------------------------------------------
    # Verifica unicità meteo
    # ---------------------------------------------------------

    meteorology_duplicates = (
        meteorology.duplicated(
            subset=[
                "year",
                "asl",
            ],
            keep=False,
        )
    )

    if meteorology_duplicates.any():
        duplicate_rows = (
            meteorology.loc[
                meteorology_duplicates,
                [
                    "year",
                    "asl",
                ],
            ]
            .drop_duplicates()
        )

        raise ValueError(
            "Il dataset meteorologico contiene "
            "chiavi anno-ASL duplicate.\n"
            f"{duplicate_rows.to_string(index=False)}"
        )

    # ---------------------------------------------------------
    # Join
    # ---------------------------------------------------------

    result = one_health.merge(
        meteorology,
        on=[
            "year",
            "asl",
        ],
        how="left",
        validate="many_to_one",
        indicator="_meteorology_merge",
    )

    # ---------------------------------------------------------
    # Disponibilità meteo
    # ---------------------------------------------------------

    result["meteo_available"] = (
        result["_meteorology_merge"]
        == "both"
    )

    result = result.drop(
        columns=[
            "_meteorology_merge",
        ]
    )

    # ---------------------------------------------------------
    # Stato qualità integrazione
    # ---------------------------------------------------------

    result[
        "integration_quality_status"
    ] = "VALID_WITHOUT_METEO"

    # Meteo presente e copertura valida
    valid_meteo = (
        result["meteo_available"]
        & (
            result["meteo_quality_status"]
            == "VALID"
        )
    )

    result.loc[
        valid_meteo,
        "integration_quality_status",
    ] = "VALID"

    # Meteo presente ma parziale
    partial_meteo = (
        result["meteo_available"]
        & (
            result["meteo_quality_status"]
            == "PARTIAL_COVERAGE"
        )
    )

    result.loc[
        partial_meteo,
        "integration_quality_status",
    ] = "VALID_WITH_PARTIAL_METEO"

    # Meteo con copertura bassa
    low_coverage_meteo = (
        result["meteo_available"]
        & (
            result["meteo_quality_status"]
            == "LOW_COVERAGE"
        )
    )

    result.loc[
        low_coverage_meteo,
        "integration_quality_status",
    ] = "VALID_WITH_LOW_METEO_COVERAGE"

    # ---------------------------------------------------------
    # Flag anno meteorologico completo
    # ---------------------------------------------------------

    if "meteo_is_full_year" not in result.columns:
        result["meteo_is_full_year"] = False

        result.loc[
            result["meteo_available"]
            & (
                result["meteo_days_available"]
                >= result["meteo_expected_days"]
            ),
            "meteo_is_full_year",
        ] = True

    # ---------------------------------------------------------
    # Informazioni dataset
    # ---------------------------------------------------------

    result[
        "master_dataset_version"
    ] = "1.0.0"

    result[
        "integration_level"
    ] = "ASL_YEAR_HEALTH_STRATUM"

    # ---------------------------------------------------------
    # Controllo chiave logica
    # ---------------------------------------------------------

    logical_key = [
        "indicator_code",
        "year",
        "asl",
        "sex",
        "age_group",
    ]

    duplicate_mask = result.duplicated(
        subset=logical_key,
        keep=False,
    )

    if duplicate_mask.any():
        duplicates = (
            result.loc[
                duplicate_mask,
                logical_key,
            ]
            .drop_duplicates()
            .head(30)
        )

        raise ValueError(
            "Il master One Health contiene "
            "chiavi logiche duplicate.\n"
            f"{duplicates.to_string(index=False)}"
        )

    # ---------------------------------------------------------
    # Ordinamento
    # ---------------------------------------------------------

    result = (
        result
        .sort_values(
            logical_key
        )
        .reset_index(drop=True)
    )

    # ---------------------------------------------------------
    # Salvataggio
    # ---------------------------------------------------------

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_parquet(
        output_path,
        index=False,
    )

    # ---------------------------------------------------------
    # Riepilogo
    # ---------------------------------------------------------

    print("=" * 70)
    print("ONE HEALTH MASTER DATASET")
    print("=" * 70)

    print(
        "Record:",
        len(result),
    )

    print(
        "Anni:",
        sorted(
            result["year"]
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        ),
    )

    print(
        "ASL:",
        sorted(
            result["asl"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        ),
    )

    print(
        "Indicatori:",
        sorted(
            result["indicator_code"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        ),
    )

    print()

    print(
        "Record con meteo:",
        int(
            result[
                "meteo_available"
            ].sum()
        ),
    )

    print(
        "Record senza meteo:",
        int(
            (
                ~result[
                    "meteo_available"
                ]
            ).sum()
        ),
    )

    print()
    print("QUALITÀ INTEGRAZIONE")

    print(
        result[
            "integration_quality_status"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print()

    print(
        "Duplicati logici:",
        int(
            result.duplicated(
                subset=logical_key,
                keep=False,
            ).sum()
        ),
    )

    print(
        "File creato:",
        output_path,
    )

    return result