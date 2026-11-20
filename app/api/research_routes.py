"""
OneHealthAI - Research API v1.

Espone esclusivamente il catalogo scientifico.
Non concede accessi al Master DSS.
"""

from fastapi import APIRouter

from app.research.artifact_repository import (
    list_research_artifacts,
)

router = APIRouter(
    prefix="/research",
    tags=["Research Panel"],
)


@router.get("/artifacts")
def research_artifacts():
    artifacts = list_research_artifacts()

    return {
        "panel": "research",
        "scientific_status": "provisional",
        "operational_use_authorized": False,
        "count": len(artifacts),
        "artifacts": artifacts,
        "notice": (
            "Gli artefatti scientifici possono "
            "contenere dati provvisori o risultati "
            "sperimentali. La loro disponibilità "
            "non implica validazione indipendente "
            "né autorizzazione all'uso operativo."
        ),
    }


# ONEHEALTHAI_BENCHMARK_API_V1

from typing import Literal

from app.research.artifact_repository import (
    read_research_artifact,
)


@router.get("/benchmarks")
def research_benchmarks(
    domain: Literal["mortality", "hospital"] = "mortality",
):
    artifact_id = {
        "mortality": "mortality_summary_csv",
        "hospital": "hospital_summary_csv",
    }[domain]

    frame = read_research_artifact(artifact_id).copy()

    baseline = (
        frame.loc[
            frame["model"] == "Persistence",
            ["outcome", "MAE"]
        ]
        .rename(columns={"MAE": "baseline_MAE"})
    )

    frame = frame.merge(
        baseline,
        on="outcome",
        how="left",
        validate="many_to_one",
    )

    frame["mae_gain_pct"] = (
        100
        * (frame["baseline_MAE"] - frame["MAE"])
        / frame["baseline_MAE"]
    )

    frame.loc[
        frame["baseline_MAE"] <= 0,
        "mae_gain_pct"
    ] = float("nan")

    frame = frame.astype(object).where(
        frame.notna(), None
    )

    return {
        "domain": domain,
        "status": "experimental",
        "operational_use_authorized": False,
        "metric": "MAE",
        "count": len(frame),
        "results": frame.to_dict(orient="records"),
        "notice": (
            "Benchmark retrospettivo esplorativo. "
            "I risultati non costituiscono validazione "
            "indipendente né evidenza causale. "
            "La scelta a posteriori del modello migliore "
            "può sovrastimare le prestazioni."
        ),
    }


# ONEHEALTHAI_PREQUENTIAL_API_V1

from app.research.artifact_repository import (
    read_research_artifact,
)
from app.research.artifact_repository import (
    list_research_artifacts,
)


@router.get("/prequential")
def research_prequential(
    domain: Literal["mortality", "hospital"] = "mortality",
):
    artifact_id = (
        f"{domain}_prequential_selection_v2_csv"
    )

    # La lettura deve avvenire esclusivamente
    # attraverso il repository scientifico.
    frame = read_research_artifact(artifact_id).copy()

    expected = {
        "domain",
        "outcome",
        "test_year",
        "selected_model",
        "selected_MAE",
        "baseline_MAE",
        "gain",
    }

    if not expected.issubset(frame.columns):
        raise ValueError(
            "Schema prequential non conforme"
        )

    frame = frame.sort_values(
        ["outcome", "test_year"]
    )

    frame = frame.astype(object).where(
        frame.notna(), None
    )

    return {
        "domain": domain,
        "status": "experimental",
        "validation_type": "retrospective_prequential_v2",
        "operational_use_authorized": False,
        "count": len(frame),
        "results": frame.to_dict(orient="records"),
        "notice": (
            "Selezione retrospettiva basata sugli errori "
            "degli anni precedenti. Non costituisce "
            "validazione esterna indipendente, "
            "né evidenza di causalità o autorizzazione "
            "all'uso operativo."
        ),
    }


# ONEHEALTHAI_ENVIRONMENT_HISTORY_V1

@router.get("/environment-history")
def research_environment_history():
    frame = read_research_artifact(
        "environment_qc_v1"
    ).copy()

    required = {
        "year",
        "asl",
        "pollutant_code",
        "mean_value",
        "analysis_eligible",
        "quality_status",
        "coverage_fraction",
    }

    if not required.issubset(frame.columns):
        raise ValueError(
            "Schema storico ambientale non conforme"
        )

    frame = frame.sort_values(
        ["asl", "pollutant_code", "year"]
    )

    columns = [
        "year",
        "asl",
        "pollutant_code",
        "mean_value",
        "analysis_eligible",
        "quality_status",
        "coverage_fraction",
    ]

    frame = frame[columns]

    frame = frame.astype(object).where(
        frame.notna(), None
    )

    return {
        "dataset": "environment_qc_v1",
        "status": "provisional",
        "operational_use_authorized": False,
        "count": len(frame),
        "years": sorted(
            frame["year"].dropna().unique().tolist()
        ),
        "territories": sorted(
            frame["asl"].dropna().unique().tolist()
        ),
        "pollutants": sorted(
            frame["pollutant_code"]
            .dropna()
            .unique()
            .tolist()
        ),
        "results": frame.to_dict(
            orient="records"
        ),
        "notice": (
            "Serie ricostruita dai file originali ARPA, concentrazioni medie in µg/m³. "
            "Media non ponderata delle medie delle stazioni con almeno il 75% dei giorni. "
            "2011–2012 esclusi per unità non documentate. La rete varia nel tempo."
        ),
    }


# ONEHEALTHAI_HEALTH_HISTORY_V1

@router.get("/health-history")
def research_health_history(
    domain: Literal["mortality", "hospital"] = "mortality",
):
    artifact_id = {
        "mortality": "mortality_qc_v1",
        "hospital": "hospital_qc_v1",
    }[domain]

    frame = read_research_artifact(artifact_id).copy()

    columns = [
        "year",
        "asl",
        "outcome",
        "metric",
        "sex",
        "value",
        "is_missing",
        "validation_status",
    ]

    missing_columns = set(columns) - set(frame.columns)

    if missing_columns:
        raise ValueError(
            f"Schema sanitario incompleto: {missing_columns}"
        )

    frame = frame[columns].sort_values(
        ["asl", "outcome", "year"]
    )

    # Non interpolare e non sostituire
    # i valori sanitari mancanti.
    frame = frame.astype(object).where(
        frame.notna(), None
    )

    return {
        "domain": domain,
        "dataset": artifact_id,
        "status": "provisional",
        "operational_use_authorized": False,
        "count": len(frame),
        "years": sorted(
            frame["year"].dropna().unique().tolist()
        ),
        "territories": sorted(
            frame["asl"].dropna().unique().tolist()
        ),
        "outcomes": sorted(
            frame["outcome"].dropna().unique().tolist()
        ),
        "results": frame.to_dict(orient="records"),
        "notice": (
            "Serie storica sanitaria ISTAT HFA "
            "per analisi scientifica esplorativa. "
            "Le definizioni ufficiali degli indicatori, "
            "la comparabilità temporale e l'equivalenza "
            "tra territori provinciali e ASL "
            "richiedono ulteriori verifiche. "
            "Nessuna autorizzazione all'uso operativo."
        ),
    }
