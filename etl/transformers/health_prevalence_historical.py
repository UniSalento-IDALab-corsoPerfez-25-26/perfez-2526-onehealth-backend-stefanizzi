"""
Historical health prevalence transformer.

Costruisce il dataset epidemiologico longitudinale OneHealthAI
integrando:

- dati sanitari aggregati per patologia;
- popolazione ISTAT per ASL, anno, sesso e fascia d'età.

Il modulo NON modifica i dataset sorgente.

La misura cases / population viene mantenuta integralmente anche
quando supera 1. In tali casi il record viene segnalato attraverso
specifici flag di compatibilità numeratore-denominatore.

Questo comportamento è intenzionale: non vengono applicati clipping,
correzioni artificiali o eliminazioni automatiche dei record.
"""

from pathlib import Path

import pandas as pd


# ============================================================
# Constants
# ============================================================

JOIN_KEYS = [
    "year",
    "asl",
    "sex",
    "age_group",
]

HEALTH_LOGICAL_KEY = [
    "indicator_code",
    "year",
    "asl",
    "sex",
    "age_group",
]

EXPECTED_ASL = {
    "BAT",
    "Bari",
    "Brindisi",
    "Foggia",
    "Lecce",
    "Taranto",
}

EXPECTED_SEXES = {
    "ALL",
    "M",
    "F",
}

EXPECTED_AGE_GROUPS = {
    "40-44",
    "45-49",
    "50-54",
    "55-59",
    "60-64",
    "65-69",
    "70-74",
    "75-79",
    "80-84",
    "85+",
}

EXPECTED_INDICATORS = {
    "BPCO",
    "DIABETES",
    "HEART_FAILURE",
    "HYPERTENSION",
}

EXPECTED_RECORDS = 10440


# ============================================================
# Main transformer
# ============================================================

def build_historical_health_prevalence(
    health_path: Path,
    population_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    """
    Costruisce il dataset epidemiologico storico ASL.

    Health
    ------
    Granularità:

        indicator × year × ASL × sex × age_group

    Demography
    ----------
    Granularità:

        year × ASL × sex × age_group

    Output
    ------
    Il dataset risultante mantiene:

    - numero di casi;
    - popolazione ISTAT;
    - rapporto casi/popolazione;
    - percentuale;
    - valore per 1.000 abitanti;
    - provenance delle due fonti;
    - quality status delle due fonti;
    - compatibilità numeratore-denominatore.

    Il join è many-to-one:

        molte osservazioni Health
        (indicatori differenti)

                ->

        una sola osservazione demografica
        per year × ASL × sex × age_group.

    Note metodologiche
    ------------------
    La quantità cases / population viene utilizzata come indicatore
    normalizzato rispetto alla popolazione ISTAT.

    Non si assume automaticamente che il numeratore sanitario e il
    denominatore ISTAT rappresentino popolazioni statisticamente
    perfettamente equivalenti.

    Se cases > population il valore NON viene modificato.
    Il record viene invece marcato come:

        denominator_compatibility =
            "INCOMPATIBLE"

        prevalence_quality_flag =
            "NUMERATOR_EXCEEDS_DENOMINATOR"

    In questo modo l'anomalia rimane osservabile e tracciabile.
    """

    # ========================================================
    # 1. Load datasets
    # ========================================================

    health = pd.read_parquet(
        health_path
    ).copy()

    population = pd.read_parquet(
        population_path
    ).copy()

    # ========================================================
    # 2. Validate input schemas
    # ========================================================

    health_required = {
        "indicator_code",
        "indicator_name",
        "year",
        "geographic_area",
        "geographic_level",
        "sex",
        "age_group",
        "cases",
        "source",
        "quality_status",
    }

    population_required = {
        "year",
        "asl",
        "sex",
        "age_group",
        "population",
        "source",
        "quality_status",
    }

    missing_health = (
        health_required.difference(
            health.columns
        )
    )

    if missing_health:
        raise ValueError(
            "Colonne mancanti nel dataset Health: "
            f"{sorted(missing_health)}"
        )

    missing_population = (
        population_required.difference(
            population.columns
        )
    )

    if missing_population:
        raise ValueError(
            "Colonne mancanti nel dataset Demography: "
            f"{sorted(missing_population)}"
        )

    # ========================================================
    # 3. Restrict Health to ASL level
    # ========================================================

    health = health[
        health["geographic_level"]
        .astype(str)
        .str.strip()
        .eq("ASL")
    ].copy()

    # Uniformiamo il nome geografico allo schema demografico.
    #
    # Manteniamo separata la provenance sanitaria.

    health = health.rename(
        columns={
            "geographic_area": "asl",
            "source": "health_source",
            "quality_status": (
                "health_quality_status"
            ),
        }
    )

    # ========================================================
    # 4. Preserve demographic provenance
    # ========================================================

    population = population.rename(
        columns={
            "source": "population_source",
            "quality_status": (
                "population_quality_status"
            ),
        }
    )

    # ========================================================
    # 5. Normalize join keys
    # ========================================================

    health["year"] = pd.to_numeric(
        health["year"],
        errors="raise",
    ).astype("int64")

    population["year"] = pd.to_numeric(
        population["year"],
        errors="raise",
    ).astype("int64")

    for column in [
        "asl",
        "sex",
        "age_group",
    ]:
        health[column] = (
            health[column]
            .astype(str)
            .str.strip()
        )

        population[column] = (
            population[column]
            .astype(str)
            .str.strip()
        )

    health["sex"] = (
        health["sex"]
        .str.upper()
    )

    population["sex"] = (
        population["sex"]
        .str.upper()
    )

    # ========================================================
    # 6. Normalize numeric variables
    # ========================================================

    health["cases"] = pd.to_numeric(
        health["cases"],
        errors="coerce",
    )

    population["population"] = (
        pd.to_numeric(
            population["population"],
            errors="coerce",
        )
    )

    # ========================================================
    # 7. Validate numeric variables before join
    # ========================================================

    if health["cases"].isna().any():
        raise ValueError(
            "Cases contiene valori nulli "
            "o non numerici."
        )

    if population["population"].isna().any():
        raise ValueError(
            "Population contiene valori nulli "
            "o non numerici."
        )

    if (health["cases"] < 0).any():
        raise ValueError(
            "Cases contiene valori negativi."
        )

    if (
        population["population"] <= 0
    ).any():
        raise ValueError(
            "Population contiene valori "
            "nulli o <= 0."
        )

    # ========================================================
    # 8. Validate expected domains
    # ========================================================

    actual_asl = set(
        health["asl"].unique()
    )

    if actual_asl != EXPECTED_ASL:
        raise ValueError(
            "Aree ASL inattese nel dataset Health: "
            f"{sorted(actual_asl)}"
        )

    population_asl = set(
        population["asl"].unique()
    )

    if population_asl != EXPECTED_ASL:
        raise ValueError(
            "Aree ASL inattese nel dataset "
            "Demography: "
            f"{sorted(population_asl)}"
        )

    actual_sexes = set(
        health["sex"].unique()
    )

    if actual_sexes != EXPECTED_SEXES:
        raise ValueError(
            "Categorie sex inattese nel dataset "
            f"Health: {sorted(actual_sexes)}"
        )

    population_sexes = set(
        population["sex"].unique()
    )

    if population_sexes != EXPECTED_SEXES:
        raise ValueError(
            "Categorie sex inattese nel dataset "
            "Demography: "
            f"{sorted(population_sexes)}"
        )

    actual_age_groups = set(
        health["age_group"].unique()
    )

    if (
        actual_age_groups
        != EXPECTED_AGE_GROUPS
    ):
        raise ValueError(
            "Fasce di età inattese nel dataset "
            "Health: "
            f"{sorted(actual_age_groups)}"
        )

    population_age_groups = set(
        population["age_group"].unique()
    )

    if (
        population_age_groups
        != EXPECTED_AGE_GROUPS
    ):
        raise ValueError(
            "Fasce di età inattese nel dataset "
            "Demography: "
            f"{sorted(population_age_groups)}"
        )

    actual_indicators = set(
        health["indicator_code"].unique()
    )

    if (
        actual_indicators
        != EXPECTED_INDICATORS
    ):
        raise ValueError(
            "Indicatori sanitari inattesi: "
            f"{sorted(actual_indicators)}"
        )

    # ========================================================
    # 9. Validate temporal coverage
    # ========================================================

    expected_indicator_years = {
        "BPCO": set(
            range(2020, 2024)
        ),
        "DIABETES": set(
            range(2006, 2024)
        ),
        "HEART_FAILURE": set(
            range(2006, 2024)
        ),
        "HYPERTENSION": set(
            range(2006, 2024)
        ),
    }

    for (
        indicator,
        expected_years,
    ) in expected_indicator_years.items():

        actual_years = set(
            health.loc[
                health["indicator_code"]
                == indicator,
                "year",
            ].unique()
        )

        if actual_years != expected_years:
            raise ValueError(
                "Copertura temporale inattesa "
                f"per {indicator}: "
                f"{sorted(actual_years)}"
            )

    # ========================================================
    # 10. Validate Health logical uniqueness
    # ========================================================

    health_duplicates = (
        health.duplicated(
            HEALTH_LOGICAL_KEY
        ).sum()
    )

    if health_duplicates:
        raise ValueError(
            "Duplicati logici nel dataset "
            "Health: "
            f"{health_duplicates}"
        )

    original_health_records = len(
        health
    )

    if (
        original_health_records
        != EXPECTED_RECORDS
    ):
        raise ValueError(
            "Cardinalità Health inattesa: "
            f"{original_health_records} "
            f"anziché {EXPECTED_RECORDS}."
        )

    # ========================================================
    # 11. Validate demographic logical uniqueness
    # ========================================================

    population_duplicates = (
        population.duplicated(
            JOIN_KEYS
        ).sum()
    )

    if population_duplicates:
        raise ValueError(
            "Il dataset demografico non è "
            "univoco sulle chiavi di join: "
            f"{population_duplicates} duplicati."
        )

    # ========================================================
    # 12. Epidemiological join
    # ========================================================

    merged = health.merge(
        population,
        on=JOIN_KEYS,
        how="left",
        validate="many_to_one",
        indicator=True,
    )

    # Il join non deve né perdere né moltiplicare
    # osservazioni Health.

    if (
        len(merged)
        != original_health_records
    ):
        raise ValueError(
            "Il join ha modificato la "
            "cardinalità Health: "
            f"{original_health_records} -> "
            f"{len(merged)}"
        )

    # ========================================================
    # 13. Detect unmatched Health records
    # ========================================================

    unmatched = (
        merged["_merge"].ne("both")
    )

    if unmatched.any():
        unmatched_count = int(
            unmatched.sum()
        )

        sample = merged.loc[
            unmatched,
            [
                "indicator_code",
                "year",
                "asl",
                "sex",
                "age_group",
            ],
        ].head(20)

        raise ValueError(
            "Osservazioni Health senza "
            "denominatore demografico: "
            f"{unmatched_count}.\n"
            "Esempio:\n"
            f"{sample.to_string(index=False)}"
        )

    merged = merged.drop(
        columns="_merge"
    )

    # ========================================================
    # 14. Post-join numeric validation
    # ========================================================

    merged["cases"] = pd.to_numeric(
        merged["cases"],
        errors="coerce",
    )

    merged["population"] = (
        pd.to_numeric(
            merged["population"],
            errors="coerce",
        )
    )

    if merged["cases"].isna().any():
        raise ValueError(
            "Cases contiene valori nulli "
            "dopo il join."
        )

    if (
        merged["population"]
        .isna()
        .any()
    ):
        raise ValueError(
            "Population contiene valori nulli "
            "dopo il join."
        )

    if (
        merged["cases"] < 0
    ).any():
        raise ValueError(
            "Cases contiene valori negativi."
        )

    if (
        merged["population"] <= 0
    ).any():
        raise ValueError(
            "Population contiene valori "
            "nulli o <= 0."
        )

    # ========================================================
    # 15. Epidemiological normalization
    # ========================================================

    merged["prevalence_proportion"] = (
        merged["cases"]
        / merged["population"]
    )

    merged["prevalence_percent"] = (
        merged["prevalence_proportion"]
        * 100.0
    )

    merged["prevalence_per_1000"] = (
        merged["prevalence_proportion"]
        * 1000.0
    )

    # Nome metodologicamente prudente da misura
    # che potrà essere utilizzata nel futuro
    # dataset ML.
    #
    # Non implica automaticamente equivalenza
    # epidemiologica perfetta tra la popolazione
    # sanitaria e il denominatore ISTAT.

    merged["normalized_health_ratio"] = (
        merged["prevalence_proportion"]
    )

    # ========================================================
    # 16. Numerator-denominator compatibility
    # ========================================================

    merged[
        "denominator_compatibility"
    ] = "COMPATIBLE"

    incompatible_denominator = (
        merged["cases"]
        > merged["population"]
    )

    merged.loc[
        incompatible_denominator,
        "denominator_compatibility",
    ] = "INCOMPATIBLE"

    # Flag specifico della misura epidemiologica.
    #
    # È separato dal quality_status dei dataset
    # sorgente perché un record può essere
    # perfettamente valido nella propria fonte
    # ma non perfettamente compatibile con una
    # fonte esterna utilizzata come denominatore.

    merged[
        "prevalence_quality_flag"
    ] = "VALID"

    merged.loc[
        incompatible_denominator,
        "prevalence_quality_flag",
    ] = "NUMERATOR_EXCEEDS_DENOMINATOR"

    # ========================================================
    # 17. Propagate source quality
    # ========================================================

    merged["quality_status"] = "VALID"

    quality_problem = (
        merged[
            "health_quality_status"
        ].ne("VALID")
        |
        merged[
            "population_quality_status"
        ].ne("VALID")
    )

    merged.loc[
        quality_problem,
        "quality_status",
    ] = "CHECK_SOURCE_QUALITY"

    # ========================================================
    # 18. Final logical validation
    # ========================================================

    final_duplicates = (
        merged.duplicated(
            HEALTH_LOGICAL_KEY
        ).sum()
    )

    if final_duplicates:
        raise ValueError(
            "Duplicati logici dopo il join: "
            f"{final_duplicates}"
        )

    if len(merged) != EXPECTED_RECORDS:
        raise ValueError(
            "Cardinalità epidemiologica "
            "inattesa: "
            f"{len(merged)} anziché "
            f"{EXPECTED_RECORDS}."
        )

    # Nessun valore di prevalenza deve essere
    # null/inf a questo punto.

    prevalence_columns = [
        "prevalence_proportion",
        "prevalence_percent",
        "prevalence_per_1000",
        "normalized_health_ratio",
    ]

    if (
        merged[prevalence_columns]
        .isna()
        .any()
        .any()
    ):
        raise ValueError(
            "Sono presenti valori nulli nelle "
            "misure epidemiologiche."
        )

    # ========================================================
    # 19. Final schema
    # ========================================================

    final_columns = [
        "indicator_code",
        "indicator_name",
        "year",
        "asl",
        "sex",
        "age_group",
        "cases",
        "population",
        "prevalence_proportion",
        "prevalence_percent",
        "prevalence_per_1000",
        "normalized_health_ratio",
        "denominator_compatibility",
        "prevalence_quality_flag",
        "health_source",
        "population_source",
        "health_quality_status",
        "population_quality_status",
        "quality_status",
    ]

    merged = (
        merged[
            final_columns
        ]
        .sort_values(
            [
                "indicator_code",
                "year",
                "asl",
                "sex",
                "age_group",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    # ========================================================
    # 20. Persist curated dataset
    # ========================================================

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    merged.to_parquet(
        output_path,
        index=False,
    )

    return merged