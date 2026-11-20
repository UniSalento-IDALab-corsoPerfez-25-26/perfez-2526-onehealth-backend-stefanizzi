from __future__ import annotations

from pathlib import Path

import pandas as pd


HEALTH_JOIN_COLUMNS = [
    "year",
    "geographic_area",
    "sex",
    "age_group",
]

POPULATION_JOIN_COLUMNS = [
    "year",
    "asl",
    "sex",
    "age_group",
]


def _validate_health_data(
    health: pd.DataFrame,
) -> None:
    required_columns = {
        "indicator_code",
        "indicator_name",
        "year",
        "geographic_level",
        "geographic_area",
        "sex",
        "age_group",
        "cases",
    }

    missing_columns = (
        required_columns
        - set(health.columns)
    )

    if missing_columns:
        raise ValueError(
            "Colonne sanitarie mancanti: "
            f"{sorted(missing_columns)}"
        )

    if health.empty:
        raise ValueError(
            "Il dataset sanitario è vuoto."
        )

    if health["cases"].isna().any():
        raise ValueError(
            "Sono presenti conteggi sanitari nulli."
        )

    if (health["cases"] < 0).any():
        raise ValueError(
            "Sono presenti conteggi sanitari negativi."
        )

    valid_sexes = {
        "M",
        "F",
        "ALL",
    }

    invalid_sexes = sorted(
        set(
            health.loc[
                ~health["sex"].isin(valid_sexes),
                "sex",
            ]
            .dropna()
            .astype(str)
            .tolist()
        )
    )

    if invalid_sexes:
        raise ValueError(
            "Valori sesso sanitari non validi: "
            f"{invalid_sexes}"
        )


def _validate_population_data(
    population: pd.DataFrame,
) -> None:
    required_columns = {
        "year",
        "asl",
        "sex",
        "age_group",
        "population",
    }

    missing_columns = (
        required_columns
        - set(population.columns)
    )

    if missing_columns:
        raise ValueError(
            "Colonne demografiche mancanti: "
            f"{sorted(missing_columns)}"
        )

    if population.empty:
        raise ValueError(
            "Il dataset demografico è vuoto."
        )

    if population["population"].isna().any():
        raise ValueError(
            "Sono presenti denominatori demografici nulli."
        )

    if (population["population"] <= 0).any():
        raise ValueError(
            "Sono presenti denominatori demografici "
            "nulli o negativi."
        )

    duplicate_mask = population.duplicated(
        subset=POPULATION_JOIN_COLUMNS,
        keep=False,
    )

    if duplicate_mask.any():
        raise ValueError(
            "Il dataset demografico contiene chiavi "
            "duplicate per anno, ASL, sesso e fascia d'età."
        )


def build_health_prevalence(
    health_path: Path,
    population_path: Path,
    output_path: Path,
    *,
    geographic_level: str = "ASL",
) -> pd.DataFrame:
    """
    Calcola la prevalenza sanitaria usando i conteggi AReSS
    e i denominatori demografici ISTAT.

    La prevalenza viene calcolata:

    - per 1.000 residenti;
    - per 100 residenti, cioè in percentuale.
    """

    if not health_path.exists():
        raise FileNotFoundError(
            f"Dataset sanitario non trovato: {health_path}"
        )

    if not population_path.exists():
        raise FileNotFoundError(
            f"Dataset demografico non trovato: {population_path}"
        )

    health = pd.read_parquet(
        health_path
    )

    population = pd.read_parquet(
        population_path
    )

    _validate_health_data(
        health
    )

    _validate_population_data(
        population
    )

    health = health[
        health["geographic_level"]
        == geographic_level
    ].copy()

    if health.empty:
        raise ValueError(
            "Nessun record sanitario trovato per il livello "
            f"geografico {geographic_level!r}."
        )

    duplicate_health_mask = health.duplicated(
        subset=[
            "indicator_code",
            *HEALTH_JOIN_COLUMNS,
        ],
        keep=False,
    )

    if duplicate_health_mask.any():
        duplicate_rows = health.loc[
            duplicate_health_mask,
            [
                "indicator_code",
                *HEALTH_JOIN_COLUMNS,
                "cases",
            ],
        ]

        raise ValueError(
            "Il dataset sanitario contiene chiavi duplicate.\n"
            f"{duplicate_rows.head(20).to_string(index=False)}"
        )

    health["cases"] = pd.to_numeric(
        health["cases"],
        errors="raise",
    ).astype("Int64")

    population["population"] = pd.to_numeric(
        population["population"],
        errors="raise",
    ).astype("Int64")

    merged = health.merge(
        population[
            [
                "year",
                "asl",
                "sex",
                "age_group",
                "population",
            ]
        ],
        left_on=HEALTH_JOIN_COLUMNS,
        right_on=POPULATION_JOIN_COLUMNS,
        how="left",
        validate="many_to_one",
        indicator=True,
    )

    unresolved = merged[
        merged["_merge"] != "both"
    ].copy()

    if not unresolved.empty:
        unresolved_keys = unresolved[
            HEALTH_JOIN_COLUMNS
        ].drop_duplicates()

        raise ValueError(
            f"{len(unresolved)} record sanitari senza "
            "denominatore ISTAT.\n"
            "Chiavi non risolte:\n"
            f"{unresolved_keys.to_string(index=False)}"
        )

    merged = merged.drop(
        columns=[
            "_merge",
            "asl",
        ]
    )

    merged["prevalence_per_1000"] = (
        merged["cases"]
        / merged["population"]
        * 1000
    )

    merged["prevalence_percent"] = (
        merged["cases"]
        / merged["population"]
        * 100
    )

    merged["prevalence_per_1000"] = (
        merged["prevalence_per_1000"]
        .round(4)
    )

    merged["prevalence_percent"] = (
        merged["prevalence_percent"]
        .round(4)
    )

    result = merged[
        [
            "indicator_code",
            "indicator_name",
            "year",
            "geographic_area",
            "sex",
            "age_group",
            "cases",
            "population",
            "prevalence_per_1000",
            "prevalence_percent",
        ]
    ].copy()

    result = result.rename(
        columns={
            "geographic_area": "asl",
        }
    )

    result["source_health"] = "AReSS"
    result["source_population"] = "ISTAT"
    result["quality_status"] = "VALID"

    result = (
        result
        .sort_values(
            [
                "indicator_code",
                "year",
                "asl",
                "sex",
                "age_group",
            ]
        )
        .reset_index(drop=True)
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_parquet(
        output_path,
        index=False,
    )

    print("=" * 70)
    print("PREVALENZE SANITARIE CALCOLATE")
    print("=" * 70)

    print(
        "Record:",
        len(result),
    )

    print(
        "Indicatori:",
        sorted(
            result["indicator_code"]
            .unique()
            .tolist()
        ),
    )

    print(
        "Anni:",
        sorted(
            result["year"]
            .astype(int)
            .unique()
            .tolist()
        ),
    )

    print(
        "ASL:",
        sorted(
            result["asl"]
            .unique()
            .tolist()
        ),
    )

    print(
        "Join non risolti: 0"
    )

    print(
        "File prodotto:",
        output_path,
    )

    return result