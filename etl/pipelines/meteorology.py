from __future__ import annotations

from pathlib import Path

import pandas as pd

from etl.clients.meteorology_ckan import (
    MeteorologyCkanClient,
)
from etl.transformers.meteorology import (
    transform_meteorological_measurements,
)
from etl.transformers.meteorology_daily import (
    build_daily_meteorology,
)


def get_rrqa_meteorology_resources(
    *,
    year: int,
) -> list[dict]:
    """
    Cerca sul catalogo CKAN il dataset RRQA Meteo
    relativo all'anno richiesto e restituisce
    tutte le risorse CSV con DataStore attivo.
    """

    client = MeteorologyCkanClient()

    queries = [
        f"dati meteo rrqa {year}",
        f"monitoraggio dati RRQA Meteo anno {year}",
    ]

    candidates: dict[str, dict] = {}

    for query in queries:
        datasets = client.search_datasets(
            query,
            rows=50,
        )

        for dataset in datasets:
            dataset_id = (
                dataset.get("name", "")
                .strip()
                .lower()
            )

            title = (
                dataset.get("title", "")
                .strip()
                .lower()
            )

            # Deve essere un dataset RRQA Meteo
            # riferibile all'anno richiesto.
            if (
                "rrqa" not in dataset_id
                and "rrqa" not in title
            ):
                continue

            if str(year) not in (
                dataset_id + " " + title
            ):
                continue

            candidates[
                dataset.get("name")
            ] = dataset

    if not candidates:
        raise ValueError(
            "Nessun dataset RRQA Meteo trovato "
            f"per l'anno {year}."
        )

    resources: list[dict] = []

    for dataset_id, dataset in candidates.items():
        for resource in dataset.get(
            "resources",
            [],
        ):
            resource_format = (
                resource.get("format", "")
                .strip()
                .upper()
            )

            datastore_active = bool(
                resource.get(
                    "datastore_active"
                )
            )

            if (
                resource_format != "CSV"
                or not datastore_active
            ):
                continue

            resource_id = resource.get("id")

            if not resource_id:
                continue

            resources.append(
                {
                    "dataset_id": dataset_id,
                    "dataset_title":
                        dataset.get("title"),
                    "resource_id": resource_id,
                    "resource_name":
                        resource.get("name"),
                    "year": year,
                }
            )

    # Elimina eventuali duplicati.
    unique = {
        resource["resource_id"]: resource
        for resource in resources
    }

    resources = list(
        unique.values()
    )

    if not resources:
        raise ValueError(
            "Dataset RRQA Meteo trovato, "
            f"ma nessuna risorsa CSV DataStore per {year}."
        )

    resources = sorted(
        resources,
        key=lambda item: (
            item["resource_name"] or ""
        ),
    )

    return resources


def run_meteorology_year(
    *,
    year: int,
    raw_root: Path = Path(
        "data/raw/meteorology"
    ),
    processed_root: Path = Path(
        "data/processed/meteorology"
    ),
) -> tuple[Path, Path]:
    """
    Pipeline completa di un anno RRQA Meteo:

    CKAN
      -> RAW
      -> hourly normalizzato
      -> daily per stazione
      -> dataset regionale hourly
      -> dataset regionale daily
    """

    client = MeteorologyCkanClient(
        timeout=120,
    )

    resources = (
        get_rrqa_meteorology_resources(
            year=year
        )
    )

    print("=" * 70)
    print(
        f"RRQA METEO {year}"
    )
    print("=" * 70)

    print(
        "Risorse trovate:",
        len(resources),
    )

    for resource in resources:
        print(
            " -",
            resource["resource_name"],
            "|",
            resource["resource_id"],
        )

    raw_dir = (
        raw_root
        / str(year)
    )

    hourly_dir = (
        processed_root
        / "hourly"
        / str(year)
    )

    daily_dir = (
        processed_root
        / "daily"
        / str(year)
    )

    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    hourly_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    daily_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    hourly_frames: list[pd.DataFrame] = []
    daily_frames: list[pd.DataFrame] = []

    failures: list[dict] = []

    for index, resource in enumerate(
        resources,
        start=1,
    ):
        resource_id = resource[
            "resource_id"
        ]

        resource_name = (
            resource.get("resource_name")
            or resource_id
        )

        safe_name = (
            resource_name
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace("(", "")
            .replace(")", "")
        )

        print()
        print(
            "-" * 70
        )

        print(
            f"[{index}/{len(resources)}] "
            f"{resource_name}"
        )

        raw_path = (
            raw_dir
            / f"{safe_name}.parquet"
        )

        hourly_path = (
            hourly_dir
            / f"{safe_name}.parquet"
        )

        daily_path = (
            daily_dir
            / f"{safe_name}_daily.parquet"
        )

        try:
            client.download_datastore_resource(
                resource_id,
                raw_path,
            )

            hourly = (
                transform_meteorological_measurements(
                    raw_path,
                    hourly_path,
                )
            )

            daily = (
                build_daily_meteorology(
                    hourly_path,
                    daily_path,
                )
            )

            hourly["resource_id"] = (
                resource_id
            )

            hourly["resource_name"] = (
                resource_name
            )

            daily["resource_id"] = (
                resource_id
            )

            daily["resource_name"] = (
                resource_name
            )

            hourly_frames.append(
                hourly
            )

            daily_frames.append(
                daily
            )

        except Exception as exc:
            failures.append(
                {
                    "resource_id":
                        resource_id,
                    "resource_name":
                        resource_name,
                    "error":
                        str(exc),
                }
            )

            print(
                "ERRORE:",
                exc,
            )

    if not hourly_frames:
        raise RuntimeError(
            "Nessuna stazione meteorologica "
            "è stata elaborata con successo."
        )

    # -------------------------------------------------
    # Dataset regionale orario
    # -------------------------------------------------

    regional_hourly = pd.concat(
        hourly_frames,
        ignore_index=True,
    )

    regional_hourly = (
        regional_hourly
        .sort_values(
            [
                "source_station_id",
                "measurement_datetime",
            ]
        )
        .reset_index(drop=True)
    )

    duplicate_hourly = (
        regional_hourly
        .duplicated(
            subset=[
                "source_station_id",
                "measurement_datetime",
            ],
            keep=False,
        )
    )

    if duplicate_hourly.any():
        raise ValueError(
            "Il dataset meteorologico regionale "
            "contiene duplicati logici tra risorse."
        )

    regional_hourly_path = (
        processed_root
        / (
            f"meteorology_rrqa_"
            f"{year}_hourly.parquet"
        )
    )

    regional_hourly.to_parquet(
        regional_hourly_path,
        index=False,
    )

    # -------------------------------------------------
    # Dataset regionale giornaliero
    # -------------------------------------------------

    regional_daily = pd.concat(
        daily_frames,
        ignore_index=True,
    )

    regional_daily = (
        regional_daily
        .sort_values(
            [
                "source_station_id",
                "measurement_date",
            ]
        )
        .reset_index(drop=True)
    )

    duplicate_daily = (
        regional_daily
        .duplicated(
            subset=[
                "source_station_id",
                "measurement_date",
            ],
            keep=False,
        )
    )

    if duplicate_daily.any():
        raise ValueError(
            "Il dataset meteorologico giornaliero "
            "regionale contiene duplicati logici."
        )

    regional_daily_path = (
        processed_root
        / (
            f"meteorology_rrqa_"
            f"{year}_daily.parquet"
        )
    )

    regional_daily.to_parquet(
        regional_daily_path,
        index=False,
    )

    # -------------------------------------------------
    # Riepilogo
    # -------------------------------------------------

    print()
    print("=" * 70)
    print(
        f"PIPELINE RRQA METEO {year} COMPLETATA"
    )
    print("=" * 70)

    print(
        "Stazioni elaborate:",
        regional_hourly[
            "source_station_id"
        ].nunique(),
    )

    print(
        "Record orari:",
        len(regional_hourly),
    )

    print(
        "Record giornalieri:",
        len(regional_daily),
    )

    print(
        "Prima data:",
        regional_hourly[
            "measurement_datetime"
        ].min(),
    )

    print(
        "Ultima data:",
        regional_hourly[
            "measurement_datetime"
        ].max(),
    )

    print(
        "Giorni distinti:",
        regional_daily[
            "measurement_date"
        ].nunique(),
    )

    print(
        "Risorse fallite:",
        len(failures),
    )

    if failures:
        print()

        for failure in failures:
            print(
                " -",
                failure[
                    "resource_name"
                ],
                ":",
                failure["error"],
            )

    print(
        "Hourly:",
        regional_hourly_path,
    )

    print(
        "Daily:",
        regional_daily_path,
    )

    return (
        regional_hourly_path,
        regional_daily_path,
    )

def get_standard_meteorology_resources(
    *,
    year: int,
) -> list[dict]:
    """
    Cerca il dataset ARPA Meteo standard
    relativo all'anno richiesto.

    Questo dataset contiene le stazioni provinciali
    Bari, Brindisi, Foggia, Lecce e Taranto.
    """

    client = MeteorologyCkanClient()

    datasets = client.search_datasets(
        f"dati meteo {year}",
        rows=50,
    )

    candidates = []

    for dataset in datasets:
        dataset_id = (
            dataset.get("name", "")
            .strip()
            .lower()
        )

        title = (
            dataset.get("title", "")
            .strip()
            .lower()
        )

        if str(year) not in (
            dataset_id + " " + title
        ):
            continue

        if "meteo" not in (
            dataset_id + " " + title
        ):
            continue

        # Escludiamo RRQA: questa funzione gestisce
        # soltanto la rete meteo standard.
        if "rrqa" in (
            dataset_id + " " + title
        ):
            continue

        candidates.append(dataset)

    if not candidates:
        raise ValueError(
            "Nessun dataset Meteo standard trovato "
            f"per l'anno {year}."
        )

    resources = []

    for dataset in candidates:
        for resource in dataset.get(
            "resources",
            [],
        ):
            if (
                resource.get(
                    "format",
                    "",
                ).upper()
                != "CSV"
            ):
                continue

            resource_id = resource.get("id")

            if not resource_id:
                continue

            resources.append(
                {
                    "dataset_id":
                        dataset.get("name"),
                    "dataset_title":
                        dataset.get("title"),
                    "resource_id":
                        resource_id,
                    "resource_name":
                        resource.get("name"),
                    "datastore_active":
                        bool(
                            resource.get(
                                "datastore_active"
                            )
                        ),
                    "year": year,
                    "network":
                        "METEO_DEDICATED",
                }
            )

    unique = {
        item["resource_id"]: item
        for item in resources
    }

    return sorted(
        unique.values(),
        key=lambda item: (
            item["resource_name"]
            or ""
        ),
    )

def run_standard_meteorology_year(
    *,
    year: int,
    raw_root: Path = Path(
        "data/raw/meteorology"
    ),
    processed_root: Path = Path(
        "data/processed/meteorology"
    ),
) -> tuple[Path, Path]:
    """
    Pipeline completa della rete ARPA Meteo standard:

    CKAN
      -> RAW
      -> hourly normalizzato
      -> daily per stazione
      -> dataset regionale hourly
      -> dataset regionale daily
    """

    client = MeteorologyCkanClient(
        timeout=120,
    )

    resources = (
        get_standard_meteorology_resources(
            year=year
        )
    )

    print("=" * 70)
    print(f"ARPA METEO STANDARD {year}")
    print("=" * 70)

    print(
        "Risorse trovate:",
        len(resources),
    )

    raw_dir = (
        raw_root
        / str(year)
        / "standard"
    )

    hourly_dir = (
        processed_root
        / "hourly"
        / str(year)
        / "standard"
    )

    daily_dir = (
        processed_root
        / "daily"
        / str(year)
        / "standard"
    )

    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    hourly_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    daily_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    hourly_frames: list[pd.DataFrame] = []
    daily_frames: list[pd.DataFrame] = []

    failures: list[dict] = []

    for index, resource in enumerate(
        resources,
        start=1,
    ):
        resource_id = (
            resource["resource_id"]
        )

        resource_name = (
            resource["resource_name"]
            or resource_id
        )

        safe_name = (
            resource_name
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace("(", "")
            .replace(")", "")
        )

        print()
        print("-" * 70)
        print(
            f"[{index}/{len(resources)}] "
            f"{resource_name}"
        )

        raw_path = (
            raw_dir
            / f"{safe_name}.parquet"
        )

        hourly_path = (
            hourly_dir
            / f"{safe_name}.parquet"
        )

        daily_path = (
            daily_dir
            / f"{safe_name}_daily.parquet"
        )

        try:
            client.download_datastore_resource(
                resource_id,
                raw_path,
            )

            hourly = (
                transform_meteorological_measurements(
                    raw_path,
                    hourly_path,
                )
            )

            daily = (
                build_daily_meteorology(
                    hourly_path,
                    daily_path,
                )
            )

            hourly["resource_id"] = resource_id
            hourly["resource_name"] = resource_name
            hourly["meteorology_network"] = (
                "METEO_STANDARD"
            )

            daily["resource_id"] = resource_id
            daily["resource_name"] = resource_name
            daily["meteorology_network"] = (
                "METEO_STANDARD"
            )

            hourly_frames.append(
                hourly
            )

            daily_frames.append(
                daily
            )

        except Exception as exc:
            failures.append(
                {
                    "resource_id":
                        resource_id,
                    "resource_name":
                        resource_name,
                    "error":
                        str(exc),
                }
            )

            print("ERRORE:", exc)

    if not hourly_frames:
        raise RuntimeError(
            "Nessuna stazione Meteo standard "
            "è stata elaborata con successo."
        )

    regional_hourly = pd.concat(
        hourly_frames,
        ignore_index=True,
    )

    regional_hourly = (
        regional_hourly
        .sort_values(
            [
                "source_station_id",
                "measurement_datetime",
            ]
        )
        .reset_index(drop=True)
    )

    hourly_duplicates = (
        regional_hourly.duplicated(
            subset=[
                "source_station_id",
                "measurement_datetime",
            ],
            keep=False,
        )
    )

    if hourly_duplicates.any():
        raise ValueError(
            "Il dataset regionale orario "
            "contiene duplicati logici."
        )

    regional_daily = pd.concat(
        daily_frames,
        ignore_index=True,
    )

    regional_daily = (
        regional_daily
        .sort_values(
            [
                "source_station_id",
                "measurement_date",
            ]
        )
        .reset_index(drop=True)
    )

    daily_duplicates = (
        regional_daily.duplicated(
            subset=[
                "source_station_id",
                "measurement_date",
            ],
            keep=False,
        )
    )

    if daily_duplicates.any():
        raise ValueError(
            "Il dataset regionale giornaliero "
            "contiene duplicati logici."
        )

    regional_hourly_path = (
        processed_root
        / (
            f"meteorology_standard_"
            f"{year}_hourly.parquet"
        )
    )

    regional_daily_path = (
        processed_root
        / (
            f"meteorology_standard_"
            f"{year}_daily.parquet"
        )
    )

    regional_hourly.to_parquet(
        regional_hourly_path,
        index=False,
    )

    regional_daily.to_parquet(
        regional_daily_path,
        index=False,
    )

    print()
    print("=" * 70)
    print(
        f"METEO STANDARD {year} COMPLETATO"
    )
    print("=" * 70)

    print(
        "Stazioni elaborate:",
        regional_hourly[
            "source_station_id"
        ].nunique(),
    )

    print(
        "Record orari:",
        len(regional_hourly),
    )

    print(
        "Record giornalieri:",
        len(regional_daily),
    )

    print(
        "Prima osservazione:",
        regional_hourly[
            "measurement_datetime"
        ].min(),
    )

    print(
        "Ultima osservazione:",
        regional_hourly[
            "measurement_datetime"
        ].max(),
    )

    print(
        "Giorni distinti:",
        regional_daily[
            "measurement_date"
        ].nunique(),
    )

    print(
        "Risorse fallite:",
        len(failures),
    )

    if failures:
        print()

        for failure in failures:
            print(
                " -",
                failure[
                    "resource_name"
                ],
                ":",
                failure["error"],
            )

    print(
        "Hourly:",
        regional_hourly_path,
    )

    print(
        "Daily:",
        regional_daily_path,
    )

    return (
        regional_hourly_path,
        regional_daily_path,
    )