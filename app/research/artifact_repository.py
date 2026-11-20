"""
OneHealthAI - Research Artifact Repository.

Accesso controllato agli artefatti scientifici.
Non espone automaticamente i risultati al Master DSS.
"""

from pathlib import Path
import json

import pandas as pd

from scripts.one_health.artifact_access import (
    resolve_artifact,
    load_registry,
    AccessDenied,
)


SUPPORTED_FORMATS = {
    ".parquet",
    ".csv",
    ".json",
}


def list_research_artifacts():
    """Elenca gli artefatti disponibili per la ricerca."""

    registry = load_registry()
    result = []

    for artifact in registry["artifacts"]:
        if artifact.get("type") not in (
            "research_dataset",
            "research_result",
            "environmental_dataset",
        ):
            continue

        try:
            path = resolve_artifact(
                artifact["id"],
                "research"
            )
        except (AccessDenied, OSError, KeyError, ValueError):
            continue

        result.append({
            "id": artifact["id"],
            "type": artifact["type"],
            "status": artifact["status"],
            "format": path.suffix,
            "master_dss_approved": artifact[
                "master_dss_approved"
            ],
        })

    return result


def read_research_artifact(artifact_id):
    """
    Legge un artefatto registrato per la ricerca.

    Non autorizza l'utilizzo nel Master DSS.
    """

    registry = load_registry()

    matches = [
        artifact
        for artifact in registry["artifacts"]
        if artifact.get("id") == artifact_id
        and artifact.get("type") in (
            "research_dataset",
            "research_result",
            "environmental_dataset",
        )
    ]

    if len(matches) != 1:
        raise AccessDenied(
            "Artefatto non disponibile per la ricerca"
        )

    path = resolve_artifact(
        artifact_id,
        "research"
    )

    if path.suffix not in SUPPORTED_FORMATS:
        raise AccessDenied(
            "Formato non autorizzato"
        )

    if path.suffix == ".parquet":
        return pd.read_parquet(path)

    if path.suffix == ".csv":
        return pd.read_csv(path)

    if path.suffix == ".json":
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    raise AccessDenied("Formato non supportato")
