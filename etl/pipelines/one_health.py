from __future__ import annotations

from pathlib import Path

import pandas as pd

from etl.transformers.health_rates import build_health_prevalence
from etl.release_guard import assert_legacy_output_writable
from etl.transformers.one_health import (
    build_environmental_exposure,
    build_one_health_dataset,
)

from etl.reporters.one_health_quality import (
    build_one_health_quality_report,
)

from etl.versioning.dataset_manifest import (
    build_dataset_manifest,
)

DEFAULT_HEALTH_FILES = [
    Path(
        "data/processed/health/"
        "bpco_2020_2023.parquet"
    ),
    Path(
        "data/processed/health/"
        "diabetes_2020_2023.parquet"
    ),
    Path(
        "data/processed/health/"
        "hypertension_2020_2023.parquet"
    ),
    Path(
        "data/processed/health/"
        "heart_failure_2020_2023.parquet"
    ),
]


def combine_health_indicators(
    source_paths: list[Path],
    output_path: Path,
) -> pd.DataFrame:
    """
    Unisce in un unico Parquet gli indicatori sanitari
    normalizzati disponibili.
    """

    existing_paths = [
        path
        for path in source_paths
        if path.exists()
    ]

    missing_paths = [
        path
        for path in source_paths
        if not path.exists()
    ]

    if missing_paths:
        print("\nDataset sanitari non ancora disponibili:")

        for path in missing_paths:
            print(" -", path)

    if not existing_paths:
        raise FileNotFoundError(
            "Nessun dataset sanitario normalizzato disponibile."
        )

    frames: list[pd.DataFrame] = []

    for path in existing_paths:
        frame = pd.read_parquet(path)

        print(
            f"Caricato {path.name}: "
            f"{len(frame)} record"
        )

        frames.append(frame)

    health = pd.concat(
        frames,
        ignore_index=True,
    )

    required_columns = {
        "indicator_code",
        "indicator_name",
        "year",
        "geographic_level",
        "geographic_area",
        "sex",
        "age_group",
        "cases",
        "source",
        "quality_status",
    }

    missing_columns = (
        required_columns - set(health.columns)
    )

    if missing_columns:
        raise ValueError(
            "Colonne sanitarie mancanti: "
            f"{sorted(missing_columns)}"
        )

    duplicate_keys = [
        "indicator_code",
        "year",
        "geographic_level",
        "geographic_area",
        "sex",
        "age_group",
    ]

    duplicate_mask = health.duplicated(
        subset=duplicate_keys,
        keep=False,
    )

    if duplicate_mask.any():
        duplicates = health.loc[
            duplicate_mask,
            duplicate_keys + ["cases"],
        ]

        raise ValueError(
            "Il dataset sanitario combinato contiene "
            "chiavi duplicate:\n"
            f"{duplicates.head(30).to_string(index=False)}"
        )

    health = (
        health
        .sort_values(duplicate_keys)
        .reset_index(drop=True)
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    health.to_parquet(
        output_path,
        index=False,
    )

    print("\nDataset sanitario combinato")
    print("Record:", len(health))
    print(
        "Indicatori:",
        sorted(
            health["indicator_code"]
            .unique()
            .tolist()
        ),
    )
    print(
        "Anni:",
        sorted(
            health["year"]
            .astype(int)
            .unique()
            .tolist()
        ),
    )
    print("File:", output_path)

    return health


def run_one_health_pipeline(
    *,
    start_year: int = 2021,
    end_year: int = 2023,
) -> Path:
    """
    Costruisce l'intero dataset analitico One Health.
    """

    if start_year > end_year:
        raise ValueError(
            "L'anno iniziale non può superare "
            "l'anno finale."
        )

    processed_health = Path(
        "data/processed/health"
    )

    processed_one_health = Path(
        "data/processed/one_health"
    )

    combined_health_path = (
        processed_health
        / "health_indicators_2020_2023.parquet"
    )

    prevalence_path = (
        processed_health
        / "health_prevalence_2020_2023.parquet"
    )

    environmental_long_path = (
        processed_one_health
        / (
            "environmental_exposure_asl_"
            f"{start_year}_{end_year}.parquet"
        )
    )

    environmental_wide_path = (
        processed_one_health
        / (
            "environmental_exposure_asl_"
            f"{start_year}_{end_year}_wide.parquet"
        )
    )

    one_health_path = (
        processed_one_health
        / (
            "one_health_dataset_"
            f"{start_year}_{end_year}.parquet"
        )
    )

    for target in (environmental_long_path, environmental_wide_path, one_health_path):
        assert_legacy_output_writable(target)

    print("=" * 70)
    print("1. COMBINAZIONE INDICATORI SANITARI")
    print("=" * 70)

    combine_health_indicators(
        DEFAULT_HEALTH_FILES,
        combined_health_path,
    )

    print()
    print("=" * 70)
    print("2. CALCOLO PREVALENZE")
    print("=" * 70)

    build_health_prevalence(
        health_path=combined_health_path,
        population_path=Path(
            "data/processed/demography/"
            "population_asl_2020_2023.parquet"
        ),
        output_path=prevalence_path,
    )

    print()
    print("=" * 70)
    print("3. ESPOSIZIONE AMBIENTALE")
    print("=" * 70)

    build_environmental_exposure(
        start_year=start_year,
        end_year=end_year,
        pollutants={
            "PM10",
            "PM2.5",
            "NO2",
            "O3",
        },
        output_long_path=environmental_long_path,
        output_wide_path=environmental_wide_path,
    )

    print()
    print("=" * 70)
    print("4. INTEGRAZIONE ONE HEALTH")
    print("=" * 70)

    build_one_health_dataset(
        health_prevalence_path=prevalence_path,
        environmental_exposure_path=(
            environmental_wide_path
        ),
        output_path=one_health_path,
        start_year=start_year,
        end_year=end_year,
    )

    print()
    print("=" * 70)
    print("5. DATA QUALITY REPORT")
    print("=" * 70)

    quality_report = build_one_health_quality_report(
        dataset_path=one_health_path,
        report_dir=Path(
            "data/reports/one_health"
        ),
        start_year=start_year,
        end_year=end_year,
        dataset_version="1.0.0",
    )


    print()
    print("=" * 70)
    print("6. VERSIONAMENTO DATASET")
    print("=" * 70)

    source_paths = [
        combined_health_path,
        prevalence_path,
        Path(
            "data/processed/demography/"
            "population_asl_2020_2023.parquet"
        ),
        environmental_long_path,
        environmental_wide_path,
    ]

    manifest = build_dataset_manifest(
        dataset_path=one_health_path,
        quality_report_path=Path(
            "data/reports/one_health/"
            "latest_quality_report.json"
        ),
        source_paths=source_paths,
        manifest_dir=Path(
            "data/manifests/one_health"
        ),
        start_year=start_year,
        end_year=end_year,
        dataset_version="1.0.0",
        pipeline_version="0.1.0",
        project_root=Path.cwd(),
    )

    if manifest["quality"]["status"] != "PASS":
        raise RuntimeError(
            "Manifest generato su un dataset "
            "che non ha superato la Data Quality."
        )

    if quality_report["status"] != "PASS":
        raise RuntimeError(
            "Il dataset One Health non ha superato "
            "i controlli di Data Quality."
        )

    print()
    print("=" * 70)
    print("PIPELINE ONE HEALTH COMPLETATA")
    print("=" * 70)
    print("Dataset finale:", one_health_path)

    return one_health_path