from __future__ import annotations

import json
from datetime import date
from pathlib import Path
import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from etl.config import settings
from etl.update_status import record_update
from etl.connectors.arpa_client import ArpaAirQualityClient
from etl.models.arpa import ArpaMeasurementQuery, IngestionMode, OutputFormat
from etl.profilers.csv_profiler import profile_csv

from pathlib import Path
from etl.transformers.measurements import transform_measurements

from etl.loaders.database import load_measurements

from etl.transformers.stations import transform_stations
from etl.transformers.pollutants import transform_pollutants

from pathlib import Path
from sqlalchemy import case

from etl.loaders.database import (
    load_measurements,
    load_pollutants,
    load_stations,
)

from etl.pipelines.one_health import (
    run_one_health_pipeline,
)

app = typer.Typer(help="Strumenti di acquisizione e profiling ARPA Puglia")
console = Console()


def show_download(result) -> None:
    table = Table(title="Download completato")
    table.add_column("Campo")
    table.add_column("Valore")
    table.add_row("File", str(result.path))
    table.add_row("URL", result.url)
    table.add_row("Dimensione", str(result.size_bytes))
    table.add_row("SHA-256", result.sha256)
    table.add_row("Content-Type", result.content_type or "n/d")
    console.print(table)


@app.command()
def stations() -> None:
    """Scarica l'anagrafica GeoJSON delle stazioni."""
    result = ArpaAirQualityClient().download_stations(settings.arpa_raw_dir / "stations.geojson")
    show_download(result)


@app.command()
def pollutants() -> None:
    """Scarica l'anagrafica CSV degli inquinanti."""
    result = ArpaAirQualityClient().download_pollutants(settings.arpa_raw_dir / "pollutants.csv")
    show_download(result)


@app.command()
def daily(
    network: str = "RRQA",
    pollutant: str | None = None,
    measurement_date: str | None = None,
    geojson: bool = False,
) -> None:
    """Scarica i dati giornalieri destinati alla dashboard."""

    parsed_date = date.fromisoformat(measurement_date) if measurement_date else None

    query = ArpaMeasurementQuery(
        mode=IngestionMode.DAILY,
        network=network,
        pollutant_label=pollutant,
        measurement_date=parsed_date,
        output_format=OutputFormat.GEOJSON if geojson else OutputFormat.CSV,
    )

    show_download(
        ArpaAirQualityClient().download_measurements(query)
    )

@app.command()
def backfill(
    year: int,
    month: int | None = None,
    network: str = "RRQA",
    pollutant: str | None = None,
    geojson: bool = False,
) -> None:
    """Scarica un periodo storico destinato alle analisi e al Machine Learning."""
    query = ArpaMeasurementQuery(
        mode=IngestionMode.BACKFILL,
        year=year,
        month=month,
        network=network,
        pollutant_label=pollutant,
        output_format=OutputFormat.GEOJSON if geojson else OutputFormat.CSV,
    )
    show_download(ArpaAirQualityClient().download_measurements(query))


@app.command()
def profile(path: Path, output: Path | None = None) -> None:
    """Analizza struttura, null, tipi e duplicati di un CSV ARPA."""
    report = profile_csv(path).to_dict()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        console.print(f"Profilo salvato in [bold]{output}[/bold]")
    else:
        console.print_json(rendered)

@app.command("transform-daily")
def transform_daily() -> None:
    """Normalizza il dataset giornaliero ARPA."""

    source = Path("data/raw/daily/measurements_rrqa_daily.csv")
    output = Path("data/processed/measurements_rrqa_daily.parquet")

    transform_measurements(source, output)


@app.command("transform-historical")
def transform_historical(
    year: int,
    month: int,
    pollutant: str = "PM10",
) -> None:
    """Normalizza un dataset storico ARPA."""

    pollutant_slug = pollutant.lower()

    source = Path(
        f"data/raw/historical/"
        f"measurements_rrqa_{year}_{month:02d}_{pollutant_slug}.csv"
    )

    output = Path(
        f"data/processed/"
        f"measurements_rrqa_{year}_{month:02d}_{pollutant_slug}.parquet"
    )

    transform_measurements(source, output)

@app.command("transform-stations")
def transform_stations_command() -> None:
    """Normalizza l'anagrafica delle stazioni ARPA."""

    transform_stations(
        Path("data/raw/stations.geojson"),
        Path("data/processed/stations.parquet"),
    )


@app.command("transform-pollutants")
def transform_pollutants_command() -> None:
    """Normalizza l'anagrafica degli inquinanti ARPA."""

    transform_pollutants(
        Path("data/raw/pollutants.csv"),
        Path("data/processed/pollutants.parquet"),
    )

@app.command("load-stations")
def load_stations_command() -> None:
    """Carica le stazioni normalizzate nel database."""
    load_stations(
        Path("data/processed/stations.parquet")
    )


@app.command("load-pollutants")
def load_pollutants_command() -> None:
    """Carica gli inquinanti normalizzati nel database."""
    load_pollutants(
        Path("data/processed/pollutants.parquet")
    )


@app.command("load-daily")
def load_daily_command() -> None:
    """Carica le misure giornaliere normalizzate nel database."""
    load_measurements(
        Path(
            "data/processed/"
            "measurements_rrqa_daily.parquet"
        )
    )


@app.command("load-historical")
def load_historical_command(
    year: int,
    month: int,
    pollutant: str = "PM10",
) -> None:
    """Carica nel database un dataset storico normalizzato."""

    pollutant_slug = pollutant.lower()

    path = Path(
        "data/processed/"
        f"measurements_rrqa_{year}_{month:02d}_{pollutant_slug}.parquet"
    )

    load_measurements(path)

@app.command("backfill-year")
def backfill_year(
    year: int,
    pollutant: str = "PM10",
    network: str = "RRQA",
) -> None:
    """
    Esegue download, trasformazione e caricamento
    di tutti i 12 mesi di un anno.
    """

    pollutant_slug = pollutant.lower()

    for month in range(1, 13):
        typer.echo(
            f"\n=== {year}-{month:02d} | {pollutant} | {network} ==="
        )

        # -------------------------------------------------
        # 1. DOWNLOAD
        # -------------------------------------------------

        query = ArpaMeasurementQuery(
            mode=IngestionMode.BACKFILL,
            year=year,
            month=month,
            network=network,
            pollutant_label=pollutant,
            output_format=OutputFormat.CSV,
        )

        try:
            download_result = (
                ArpaAirQualityClient()
                .download_measurements(query)
            )

            show_download(download_result)

        except Exception as exc:
            typer.echo(
                f"ERRORE DOWNLOAD {year}-{month:02d}: {exc}"
            )
            continue

        # -------------------------------------------------
        # 2. TRANSFORM
        # -------------------------------------------------

        raw_path = Path(
            "data/raw/historical/"
            f"measurements_{network.lower()}_"
            f"{year}_{month:02d}_{pollutant_slug}.csv"
        )

        processed_path = Path(
            "data/processed/"
            f"measurements_{network.lower()}_"
            f"{year}_{month:02d}_{pollutant_slug}.parquet"
        )

        try:
            transform_measurements(
                raw_path,
                processed_path,
            )

        except Exception as exc:
            typer.echo(
                f"ERRORE TRANSFORM {year}-{month:02d}: {exc}"
            )
            continue

        # -------------------------------------------------
        # 3. LOAD
        # -------------------------------------------------

        try:
            load_measurements(
                processed_path
            )

        except Exception as exc:
            typer.echo(
                f"ERRORE LOAD {year}-{month:02d}: {exc}"
            )
            continue

        typer.echo(
            f"OK {year}-{month:02d}"
        )

@app.command("backfill-all")
def backfill_all(
    year: int,
    network: str = "RRQA",
) -> None:
    """
    Esegue il backfill annuale per tutti gli inquinanti
    presenti nell'anagrafica normalizzata.
    """

    pollutants_path = Path(
        "data/processed/pollutants.parquet"
    )

    if not pollutants_path.exists():
        raise typer.BadParameter(
            "File pollutants.parquet non trovato. "
            "Esegui prima arpa transform-pollutants."
        )

    pollutants_df = pd.read_parquet(
        pollutants_path
    )

    pollutant_codes = (
        pollutants_df["code"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
        .tolist()
    )

    typer.echo(
        f"Inquinanti rilevati: "
        f"{', '.join(pollutant_codes)}"
    )

    for pollutant in pollutant_codes:

        typer.echo(
            "\n"
            + "=" * 70
        )

        typer.echo(
            f"BACKFILL {year} - {pollutant}"
        )

        typer.echo(
            "=" * 70
        )

        pollutant_slug = (
            pollutant
            .lower()
            .replace(" ", "_")
        )

        for month in range(1, 13):

            typer.echo(
                f"\n--- "
                f"{year}-{month:02d} "
                f"{pollutant} "
                f"---"
            )

            # ---------------------------------------------
            # DOWNLOAD
            # ---------------------------------------------

            query = ArpaMeasurementQuery(
                mode=IngestionMode.BACKFILL,
                year=year,
                month=month,
                network=network,
                pollutant_label=pollutant,
                output_format=OutputFormat.CSV,
            )

            try:
                result = (
                    ArpaAirQualityClient()
                    .download_measurements(query)
                )

                show_download(result)

            except Exception as exc:
                typer.echo(
                    f"DOWNLOAD FALLITO: {exc}"
                )
                continue

            # ---------------------------------------------
            # PATH
            # ---------------------------------------------

            raw_path = Path(
                "data/raw/historical/"
                f"measurements_"
                f"{network.lower()}_"
                f"{year}_"
                f"{month:02d}_"
                f"{pollutant_slug}.csv"
            )

            processed_path = Path(
                "data/processed/"
                f"measurements_"
                f"{network.lower()}_"
                f"{year}_"
                f"{month:02d}_"
                f"{pollutant_slug}.parquet"
            )

            # ---------------------------------------------
            # TRANSFORM
            # ---------------------------------------------

            try:
                transform_measurements(
                    raw_path,
                    processed_path,
                )

            except Exception as exc:
                typer.echo(
                    f"TRANSFORM FALLITO: {exc}"
                )
                continue

            # ---------------------------------------------
            # LOAD
            # ---------------------------------------------

            try:
                load_measurements(
                    processed_path
                )

            except Exception as exc:
                typer.echo(
                    f"LOAD FALLITO: {exc}"
                )
                continue

            typer.echo(
                f"OK: "
                f"{year}-{month:02d} "
                f"{pollutant}"
            )

@app.command("coverage")
def coverage() -> None:
    """
    Mostra la copertura dei dati ambientali presenti nel database.
    """

    from sqlalchemy import func, select

    from app.core.database import SessionLocal
    from app.models import (
        EnvironmentalMeasurement,
        MonitoringStation,
        Pollutant,
    )

    with SessionLocal() as session:
        query = (
            select(
                func.extract(
                    "year",
                    EnvironmentalMeasurement.measurement_date,
                ).label("year"),
                func.extract(
                    "month",
                    EnvironmentalMeasurement.measurement_date,
                ).label("month"),
                Pollutant.code.label("pollutant"),
                func.count(
                    EnvironmentalMeasurement.id
                ).label("measurements"),
                func.count(
                    func.distinct(
                        EnvironmentalMeasurement.measurement_date
                    )
                ).label("days"),
                func.count(
                    func.distinct(
                        EnvironmentalMeasurement.station_id
                    )
                ).label("stations"),
                func.sum(
                    case(
                        (
                            EnvironmentalMeasurement.quality_status
                            == "VALID_WITH_WARNING",
                            1,
                        ),
                        else_=0,
                    )
                ).label("warnings"),
                func.sum(
                    case(
                        (
                            EnvironmentalMeasurement.quality_status
                            == "DUPLICATE_IDENTICAL",
                            1,
                        ),
                        else_=0,
                    )
                ).label("duplicates"),
            )
            .join(
                Pollutant,
                Pollutant.id
                == EnvironmentalMeasurement.pollutant_id,
            )
            .join(
                MonitoringStation,
                MonitoringStation.id
                == EnvironmentalMeasurement.station_id,
            )
            .group_by(
                "year",
                "month",
                Pollutant.code,
            )
            .order_by(
                "year",
                "month",
                Pollutant.code,
            )
        )

        rows = session.execute(query).all()

    if not rows:
        typer.echo("Nessun dato ambientale disponibile.")
        return

    data = [
        {
            "year": int(row.year),
            "month": int(row.month),
            "pollutant": row.pollutant,
            "measurements": row.measurements,
            "days": row.days,
            "stations": row.stations,
            "warnings": row.warnings or 0,
            "duplicates": row.duplicates or 0,
        }
        for row in rows
    ]

    frame = pd.DataFrame(data)

    typer.echo()
    typer.echo(frame.to_string(index=False))

@app.command("daily-pipeline")
def daily_pipeline(
    network: str = "RRQA",
) -> None:
    """
    Esegue l'intera pipeline giornaliera ARPA:
    download -> transform -> load.
    """

    typer.echo(
        f"\nAvvio pipeline giornaliera ARPA - rete {network}"
    )

    # -------------------------------------------------
    # DOWNLOAD
    # -------------------------------------------------

    record_update("RUNNING", "DOWNLOAD")
    query = ArpaMeasurementQuery(
        mode=IngestionMode.DAILY,
        network=network,
        output_format=OutputFormat.CSV,
    )

    try:
        result = (
            ArpaAirQualityClient()
            .download_measurements(query)
        )

        show_download(result)

    except Exception as exc:
        record_update("FAILED", "DOWNLOAD")
        typer.echo(
            f"DOWNLOAD FALLITO: {exc}"
        )
        raise typer.Exit(code=1)

    # -------------------------------------------------
    # PATH
    # -------------------------------------------------

    raw_path = Path(
        "data/raw/daily/"
        f"measurements_{network.lower()}_daily.csv"
    )

    processed_path = Path(
        "data/processed/"
        f"measurements_{network.lower()}_daily.parquet"
    )

    # -------------------------------------------------
    # TRANSFORM
    # -------------------------------------------------

    try:
        transform_measurements(
            raw_path,
            processed_path,
        )

    except Exception as exc:
        record_update("FAILED", "TRANSFORM")
        typer.echo(
            f"TRANSFORM FALLITO: {exc}"
        )
        raise typer.Exit(code=1)

    # -------------------------------------------------
    # LOAD
    # -------------------------------------------------

    try:
        load_measurements(
            processed_path
        )

    except Exception as exc:
        record_update("FAILED", "LOAD")
        typer.echo(
            f"LOAD FALLITO: {exc}"
        )
        raise typer.Exit(code=1)

    dates = pd.to_datetime(pd.read_parquet(processed_path)["measurement_date"], errors="coerce")
    latest = dates.max()
    record_update("OK", "COMPLETE", latest.date().isoformat() if pd.notna(latest) else None)
    typer.echo()
    typer.echo(
        "Pipeline giornaliera completata con successo."
    )

@app.command("build-one-health")
def build_one_health_command(
    start_year: int = 2021,
    end_year: int = 2023,
) -> None:
    """
    Costruisce il dataset analitico integrato
    ambiente-salute.
    """

    path = run_one_health_pipeline(
        start_year=start_year,
        end_year=end_year,
    )

    typer.echo("")
    typer.echo(
        f"Dataset One Health creato: {path}"
    )

if __name__ == "__main__":
    app()
