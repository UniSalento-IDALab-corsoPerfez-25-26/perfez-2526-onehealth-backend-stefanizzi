from __future__ import annotations
from pathlib import Path

import pandas as pd

from etl.parsers.demography import parse_istat_population



import csv
import re

PROVINCE_TO_ASL = {
    "071": "Foggia",
    "072": "Bari",
    "073": "Taranto",
    "074": "Brindisi",
    "075": "Lecce",
    "110": "BAT",
}


def _validate_population(
    population: pd.DataFrame,
    *,
    year: int,
) -> None:
    """
    Esegue i controlli minimi di qualità sui dati demografici.
    """

    required_columns = {
        "year",
        "province_code",
        "municipality_code",
        "municipality",
        "sex",
        "age",
        "age_group",
        "population",
        "source",
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
            f"Nessun record demografico per l'anno {year}."
        )

    unexpected_years = set(
        population["year"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    if unexpected_years != {year}:
        raise ValueError(
            f"Anni inattesi nel dataset {year}: "
            f"{sorted(unexpected_years)}"
        )

    if population["municipality_code"].isna().any():
        raise ValueError(
            "Sono presenti codici comunali mancanti."
        )

    if population["population"].isna().any():
        raise ValueError(
            "Sono presenti valori di popolazione mancanti."
        )

    if (
        population["population"] < 0
    ).any():
        raise ValueError(
            "Sono presenti valori di popolazione negativi."
        )

    valid_sexes = {
        "M",
        "F",
        "ALL",
    }

    unexpected_sexes = set(
        population.loc[
            ~population["sex"].isin(valid_sexes),
            "sex",
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if unexpected_sexes:
        raise ValueError(
            "Valori sesso non riconosciuti: "
            f"{sorted(unexpected_sexes)}"
        )

    duplicate_columns = [
        "year",
        "municipality_code",
        "sex",
        "age",
    ]

    duplicate_mask = population.duplicated(
        subset=duplicate_columns,
        keep=False,
    )

    if duplicate_mask.any():
        duplicate_count = int(
            duplicate_mask.sum()
        )

        raise ValueError(
            f"Trovati {duplicate_count} record "
            "demografici con chiave duplicata."
        )


def _assign_asl(
    population: pd.DataFrame,
) -> pd.DataFrame:
    """
    Associa ciascun comune alla ASL corrispondente
    utilizzando il codice provincia ISTAT.
    """

    result = population.copy()

    result["asl"] = (
        result["province_code"]
        .astype("string")
        .str.strip()
        .map(PROVINCE_TO_ASL)
    )

    missing_asl = result[
        result["asl"].isna()
    ]

    if not missing_asl.empty:
        missing_codes = sorted(
            missing_asl["province_code"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        raise ValueError(
            "Codici provincia senza mapping ASL: "
            f"{missing_codes}"
        )

    return result


def _build_asl_population(
    population: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aggrega la popolazione comunale nelle classi
    ASL × anno × sesso × fascia d'età.
    """

    health_population = population[
        population["age_group"].notna()
    ].copy()

    if health_population.empty:
        raise ValueError(
            "Nessun record demografico compatibile "
            "con le fasce d'età sanitarie."
        )

    asl_population = (
        health_population
        .groupby(
            [
                "year",
                "asl",
                "sex",
                "age_group",
            ],
            as_index=False,
            dropna=False,
        )
        ["population"]
        .sum()
    )

    asl_population["population"] = (
        asl_population["population"]
        .astype("Int64")
    )

    asl_population["source"] = "ISTAT"
    asl_population["quality_status"] = "VALID"

    asl_population = (
        asl_population
        .sort_values(
            [
                "year",
                "asl",
                "sex",
                "age_group",
            ]
        )
        .reset_index(drop=True)
    )

    expected_asl = {
        "Bari",
        "BAT",
        "Brindisi",
        "Foggia",
        "Lecce",
        "Taranto",
    }

    actual_asl = set(
        asl_population["asl"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    missing_asl = (
        expected_asl
        - actual_asl
    )

    if missing_asl:
        raise ValueError(
            "ASL mancanti nel dataset aggregato: "
            f"{sorted(missing_asl)}"
        )

    return asl_population


def transform_puglia_population(
    source_paths: list[Path],
    output_detail_path: Path,
    output_asl_path: Path,
    *,
    year: int,
) -> None:
    """
    Trasforma i file provinciali ISTAT di un singolo anno.

    Produce:
    1. un dataset comunale dettagliato;
    2. un dataset aggregato per ASL, sesso e fascia d'età.
    """

    if not source_paths:
        raise ValueError(
            "Nessun file ISTAT fornito."
        )

    frames: list[pd.DataFrame] = []

    for path in source_paths:
        if not path.exists():
            raise FileNotFoundError(
                f"File ISTAT non trovato: {path}"
            )

        frame = parse_istat_population(
            path,
            year=year,
        )

        frames.append(frame)

    population = pd.concat(
        frames,
        ignore_index=True,
    )

    _validate_population(
        population,
        year=year,
    )

    population = _assign_asl(
        population
    )

    population["quality_status"] = "VALID"

    population = (
        population
        .sort_values(
            [
                "year",
                "province_code",
                "municipality_code",
                "sex",
                "age",
            ]
        )
        .reset_index(drop=True)
    )

    asl_population = _build_asl_population(
        population
    )

    output_detail_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_asl_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    population.to_parquet(
        output_detail_path,
        index=False,
    )

    asl_population.to_parquet(
        output_asl_path,
        index=False,
    )

    print(
        f"Anno elaborato: {year}"
    )

    print(
        f"File sorgente: {len(source_paths)}"
    )

    print(
        "Record comunali dettagliati: "
        f"{len(population)}"
    )

    print(
        "Comuni distinti: "
        f"{population['municipality_code'].nunique()}"
    )

    print(
        "Record aggregati ASL: "
        f"{len(asl_population)}"
    )

    print(
        "ASL: "
        f"{sorted(asl_population['asl'].unique())}"
    )

    print(
        f"File dettagliato: {output_detail_path}"
    )

    print(
        f"File ASL: {output_asl_path}"
    )


def transform_population_years(
    source_by_year: dict[int, list[Path]],
    output_detail_path: Path,
    output_asl_path: Path,
) -> None:
    """
    Trasforma più annualità ISTAT.

    Parametri
    ----------
    source_by_year:
        Dizionario nel formato:
        {
            2020: [file provincia 1, ...],
            2021: [file provincia 1, ...],
        }

    output_detail_path:
        Percorso del Parquet comunale multi-anno.

    output_asl_path:
        Percorso del Parquet aggregato ASL multi-anno.
    """

    if not source_by_year:
        raise ValueError(
            "Nessuna annualità ISTAT fornita."
        )

    detail_frames: list[pd.DataFrame] = []
    asl_frames: list[pd.DataFrame] = []

    for year, source_paths in sorted(
        source_by_year.items()
    ):
        print()
        print(
            "=" * 70
        )
        print(
            f"Elaborazione ISTAT {year}"
        )
        print(
            "=" * 70
        )

        if not source_paths:
            raise ValueError(
                f"Nessun file ISTAT disponibile "
                f"per l'anno {year}."
            )

        frames: list[pd.DataFrame] = []

        for path in source_paths:
            if not path.exists():
                raise FileNotFoundError(
                    f"File ISTAT non trovato: {path}"
                )

            frame = parse_istat_population(
                path,
                year=year,
            )

            frames.append(frame)

        population = pd.concat(
            frames,
            ignore_index=True,
        )

        _validate_population(
            population,
            year=year,
        )

        population = _assign_asl(
            population
        )

        population["quality_status"] = "VALID"

        population = (
            population
            .sort_values(
                [
                    "year",
                    "province_code",
                    "municipality_code",
                    "sex",
                    "age",
                ]
            )
            .reset_index(drop=True)
        )

        asl_population = _build_asl_population(
            population
        )

        detail_frames.append(
            population
        )

        asl_frames.append(
            asl_population
        )

        print(
            f"File provinciali: {len(source_paths)}"
        )

        print(
            "Comuni distinti: "
            f"{population['municipality_code'].nunique()}"
        )

        print(
            "Record comunali: "
            f"{len(population)}"
        )

        print(
            "Record ASL: "
            f"{len(asl_population)}"
        )

    detail = pd.concat(
        detail_frames,
        ignore_index=True,
    )

    asl = pd.concat(
        asl_frames,
        ignore_index=True,
    )

    detail = (
        detail
        .sort_values(
            [
                "year",
                "province_code",
                "municipality_code",
                "sex",
                "age",
            ]
        )
        .reset_index(drop=True)
    )

    asl = (
        asl
        .sort_values(
            [
                "year",
                "asl",
                "sex",
                "age_group",
            ]
        )
        .reset_index(drop=True)
    )

    detail_duplicate_columns = [
        "year",
        "municipality_code",
        "sex",
        "age",
    ]

    if detail.duplicated(
        subset=detail_duplicate_columns
    ).any():
        raise ValueError(
            "Il dataset comunale multi-anno "
            "contiene chiavi duplicate."
        )

    asl_duplicate_columns = [
        "year",
        "asl",
        "sex",
        "age_group",
    ]

    if asl.duplicated(
        subset=asl_duplicate_columns
    ).any():
        raise ValueError(
            "Il dataset ASL multi-anno "
            "contiene chiavi duplicate."
        )

    output_detail_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_asl_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    detail.to_parquet(
        output_detail_path,
        index=False,
    )

    asl.to_parquet(
        output_asl_path,
        index=False,
    )

    print()
    print(
        "=" * 70
    )
    print(
        "Trasformazione demografica completata"
    )
    print(
        "=" * 70
    )

    print(
        "Anni elaborati: "
        f"{sorted(asl['year'].unique().tolist())}"
    )

    print(
        "Record comunali totali: "
        f"{len(detail)}"
    )

    print(
        "Record ASL totali: "
        f"{len(asl)}"
    )

    print(
        "Comuni distinti complessivi: "
        f"{detail['municipality_code'].nunique()}"
    )

    print(
        f"File dettagliato: {output_detail_path}"
    )

    print(
        f"File ASL: {output_asl_path}"
    )




HISTORICAL_PROVINCE_TO_ASL = {
    "071": "Foggia",
    "072": "Bari",
    "073": "Taranto",
    "074": "Brindisi",
    "075": "Lecce",
    "110": "BAT",
}

HISTORICAL_AGE_GROUPS = {
    "40-44": range(40, 45),
    "45-49": range(45, 50),
    "50-54": range(50, 55),
    "55-59": range(55, 60),
    "60-64": range(60, 65),
    "65-69": range(65, 70),
    "70-74": range(70, 75),
    "75-79": range(75, 80),
    "80-84": range(80, 85),
    "85+": range(85, 101),
}

HISTORICAL_SEX_MAP = {
    "Totale": "ALL",
    "Maschi": "M",
    "Femmine": "F",
}


def parse_istat_historical_provinces(
    source_path: Path,
    start_year: int = 2006,
    end_year: int = 2019,
) -> pd.DataFrame:
    """
    Parse the ISTAT intercensal population reconstruction
    by province, sex and single year of age.

    Only the 'Tutte le cittadinanze' blocks are used.

    Returns one record for:
        year × ASL × sex × age

    restricted to ages 40-100 and the six Apulian
    provinces used by the OneHealth model.
    """

    with source_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        lines = [
            line.rstrip("\r\n")
            for line in handle
        ]

    records: list[dict] = []

    current_year: int | None = None
    current_citizenship: str | None = None
    age_columns: list[int] | None = None
    current_sex: str | None = None

    year_pattern = re.compile(
        r'^(?:"?)(.+?)\s*-\s*Anno:\s*(\d{4})(?:"?)$'
    )

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        clean = stripped.strip('"')

        year_match = year_pattern.match(clean)

        if year_match:
            current_citizenship = (
                year_match.group(1).strip()
            )
            current_year = int(
                year_match.group(2)
            )
            age_columns = None
            current_sex = None
            continue

        if (
            current_citizenship
            != "Tutte le cittadinanze"
        ):
            continue

        if current_year is None:
            continue

        if not (
            start_year
            <= current_year
            <= end_year
        ):
            continue

        if clean.startswith("Territorio/Et"):
            row = next(
                csv.reader(
                    [clean],
                    delimiter=";",
                )
            )

            age_columns = []

            for value in row[2:]:
                value = value.strip()

                if value.isdigit():
                    age_columns.append(int(value))

            current_sex = None
            continue

        if clean.startswith(
            "Codice provincia;Provincia;"
        ):
            row = next(
                csv.reader(
                    [clean],
                    delimiter=";",
                )
            )

            if len(row) < 3:
                current_sex = None
                continue

            current_sex = (
                HISTORICAL_SEX_MAP.get(
                    row[2].strip()
                )
            )
            continue

        if (
            age_columns is None
            or current_sex is None
        ):
            continue

        row = next(
            csv.reader(
                [clean],
                delimiter=";",
            )
        )

        if len(row) < 3:
            continue

        province_code = row[0].strip()

        if (
            province_code
            not in HISTORICAL_PROVINCE_TO_ASL
        ):
            continue

        values = row[2:]

        if len(values) != len(age_columns):
            raise ValueError(
                "Numero valori età inatteso "
                f"per anno={current_year}, "
                f"provincia={province_code}, "
                f"sex={current_sex}: "
                f"{len(values)} valori contro "
                f"{len(age_columns)} età."
            )

        asl = HISTORICAL_PROVINCE_TO_ASL[
            province_code
        ]

        for age, value in zip(
            age_columns,
            values,
            strict=True,
        ):
            if age < 40:
                continue

            value = value.strip()

            if value == "":
                population = pd.NA
            else:
                population = pd.to_numeric(
                    value,
                    errors="coerce",
                )

            records.append(
                {
                    "year": current_year,
                    "geographic_level": "ASL",
                    "geographic_area": asl,
                    "sex": current_sex,
                    "age": age,
                    "population": population,
                    "source": (
                        "ISTAT_POPULATION_"
                        "RECONSTRUCTION"
                    ),
                }
            )

    frame = pd.DataFrame(records)

    if frame.empty:
        raise ValueError(
            "Nessun record demografico storico "
            "ISTAT estratto."
        )

    frame["year"] = (
        pd.to_numeric(
            frame["year"],
            errors="raise",
        )
        .astype("int64")
    )

    frame["age"] = (
        pd.to_numeric(
            frame["age"],
            errors="raise",
        )
        .astype("int64")
    )

    frame["population"] = pd.to_numeric(
        frame["population"],
        errors="coerce",
    )

    return frame.sort_values(
        [
            "year",
            "geographic_area",
            "sex",
            "age",
        ]
    ).reset_index(drop=True)


def aggregate_historical_population_age_groups(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aggregate single-year ages into the same age groups
    used by the historical health dataset.
    """

    work = frame.copy()

    def age_group(age: int) -> str | None:
        for label, ages in (
            HISTORICAL_AGE_GROUPS.items()
        ):
            if age in ages:
                return label

        return None

    work["age_group"] = (
        work["age"]
        .map(age_group)
        .astype("string")
    )

    work = work[
        work["age_group"].notna()
    ].copy()

    group_columns = [
        "year",
        "geographic_level",
        "geographic_area",
        "sex",
        "age_group",
        "source",
    ]

    result = (
        work.groupby(
            group_columns,
            as_index=False,
            observed=True,
        )
        .agg(
            population=(
                "population",
                lambda values: (
                    values.sum(min_count=1)
                ),
            )
        )
    )

    result["quality_status"] = "VALID"

    expected_age_groups = set(
        HISTORICAL_AGE_GROUPS
    )

    actual_age_groups = set(
        result["age_group"]
        .dropna()
        .astype(str)
        .unique()
    )

    if actual_age_groups != expected_age_groups:
        raise ValueError(
            "Age groups storici inattesi: "
            f"{sorted(actual_age_groups)}"
        )

    return result[
        [
            "year",
            "geographic_level",
            "geographic_area",
            "sex",
            "age_group",
            "population",
            "source",
            "quality_status",
        ]
    ].sort_values(
        [
            "year",
            "geographic_area",
            "sex",
            "age_group",
        ]
    ).reset_index(drop=True)

def build_historical_population_2006_2023(
    historical_source_path: Path,
    current_population_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    """
    Costruisce il dataset demografico storico ASL 2006-2023.

    2006-2019:
        ISTAT Ricostruzione intercensuaria (RIC)

    2020-2023:
        dataset demografico corrente già validato (POS)

    Output granularity:
        year × ASL × sex × age_group

    Output schema:
        year, asl, sex, age_group, population, source, quality_status
    """

    # ---------------------------------------------------------
    # 1. Historical population: ISTAT RIC 2006-2019
    # ---------------------------------------------------------

    historical_detail = parse_istat_historical_provinces(
        historical_source_path,
        start_year=2006,
        end_year=2019,
    )

    historical = aggregate_historical_population_age_groups(
        historical_detail
    ).copy()

    historical_required = {
        "year",
        "geographic_area",
        "sex",
        "age_group",
        "population",
        "source",
        "quality_status",
    }

    missing = historical_required.difference(
        historical.columns
    )

    if missing:
        raise ValueError(
            "Colonne mancanti nel dataset demografico "
            f"storico: {sorted(missing)}"
        )

    # Lo storico aggregato è provinciale/ASL.
    # Uniformiamo soltanto il nome della colonna geografica
    # allo schema del dataset corrente.
    historical = historical.rename(
        columns={"geographic_area": "asl"}
    )

    historical = historical[
        historical["year"].between(2006, 2019)
    ].copy()

    # ---------------------------------------------------------
    # 2. Current population: ISTAT POS 2020-2023
    # ---------------------------------------------------------

    current = pd.read_parquet(
        current_population_path
    ).copy()

    final_columns = [
        "year",
        "asl",
        "sex",
        "age_group",
        "population",
        "source",
        "quality_status",
    ]

    missing = set(final_columns).difference(
        current.columns
    )

    if missing:
        raise ValueError(
            "Colonne mancanti nel dataset demografico "
            f"corrente: {sorted(missing)}"
        )

    current = current[
        current["year"].between(2020, 2023)
    ].copy()

    # ---------------------------------------------------------
    # 3. Uniform schema
    # ---------------------------------------------------------

    historical = historical[final_columns].copy()
    current = current[final_columns].copy()

    combined = pd.concat(
        [historical, current],
        ignore_index=True,
    )

    # ---------------------------------------------------------
    # 4. Type normalization
    # ---------------------------------------------------------

    combined["year"] = pd.to_numeric(
        combined["year"],
        errors="raise",
    ).astype("int64")

    combined["population"] = pd.to_numeric(
        combined["population"],
        errors="coerce",
    )

    combined["asl"] = (
        combined["asl"]
        .astype(str)
        .str.strip()
    )

    combined["sex"] = (
        combined["sex"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    combined["age_group"] = (
        combined["age_group"]
        .astype(str)
        .str.strip()
    )

    # ---------------------------------------------------------
    # 5. Structural validation
    # ---------------------------------------------------------

    expected_years = set(range(2006, 2024))

    expected_areas = {
        "BAT",
        "Bari",
        "Brindisi",
        "Foggia",
        "Lecce",
        "Taranto",
    }

    expected_sexes = {
        "ALL",
        "M",
        "F",
    }

    expected_age_groups = set(
        HISTORICAL_AGE_GROUPS
    )

    actual_years = set(
        combined["year"].unique()
    )

    if actual_years != expected_years:
        raise ValueError(
            "Copertura temporale inattesa: "
            f"{sorted(actual_years)}"
        )

    actual_areas = set(
        combined["asl"].unique()
    )

    if actual_areas != expected_areas:
        raise ValueError(
            "Aree ASL inattese nel dataset "
            f"demografico storico: {sorted(actual_areas)}"
        )

    actual_sexes = set(
        combined["sex"].unique()
    )

    if actual_sexes != expected_sexes:
        raise ValueError(
            "Categorie sex inattese nel dataset "
            f"demografico storico: {sorted(actual_sexes)}"
        )

    actual_age_groups = set(
        combined["age_group"].unique()
    )

    if actual_age_groups != expected_age_groups:
        raise ValueError(
            "Fasce di età inattese nel dataset "
            f"demografico storico: "
            f"{sorted(actual_age_groups)}"
        )

    # ---------------------------------------------------------
    # 6. Population validation
    # ---------------------------------------------------------

    if combined["population"].isna().any():
        raise ValueError(
            "Population contiene valori nulli."
        )

    if (combined["population"] < 0).any():
        raise ValueError(
            "Population contiene valori negativi."
        )

    # ---------------------------------------------------------
    # 7. Logical duplicates
    # ---------------------------------------------------------

    key = [
        "year",
        "asl",
        "sex",
        "age_group",
    ]

    duplicates = combined.duplicated(
        key
    ).sum()

    if duplicates:
        raise ValueError(
            "Duplicati logici nel dataset "
            f"demografico storico: {duplicates}"
        )

    # ---------------------------------------------------------
    # 8. Expected cardinality
    # ---------------------------------------------------------

    expected_records = (
        len(expected_years)
        * len(expected_areas)
        * len(expected_sexes)
        * len(expected_age_groups)
    )

    if len(combined) != expected_records:
        raise ValueError(
            "Cardinalità inattesa: "
            f"{len(combined)} anziché "
            f"{expected_records}."
        )

    # ---------------------------------------------------------
    # 9. Epidemiological consistency:
    #    ALL population must equal M + F
    # ---------------------------------------------------------

    all_population = (
        combined[
            combined["sex"] == "ALL"
        ]
        .set_index(
            ["year", "asl", "age_group"]
        )["population"]
        .sort_index()
    )

    mf_population = (
        combined[
            combined["sex"].isin(["M", "F"])
        ]
        .groupby(
            ["year", "asl", "age_group"]
        )["population"]
        .sum()
        .sort_index()
    )

    population_difference = (
        all_population.subtract(
            mf_population
        )
    )

    if population_difference.isna().any():
        raise ValueError(
            "Impossibile verificare ALL = M + F: "
            "combinazioni demografiche mancanti."
        )

    if not (
        population_difference.abs() < 1e-9
    ).all():
        max_difference = (
            population_difference
            .abs()
            .max()
        )

        raise ValueError(
            "Incoerenza demografica: "
            "ALL != M + F. "
            f"Differenza massima: {max_difference}"
        )

    # ---------------------------------------------------------
    # 10. Sort and persist
    # ---------------------------------------------------------

    combined = combined.sort_values(
        [
            "year",
            "asl",
            "sex",
            "age_group",
        ]
    ).reset_index(drop=True)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_parquet(
        output_path,
        index=False,
    )

    return combined