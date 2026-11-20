from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def calculate_sha256(
    path: Path,
    *,
    chunk_size: int = 1024 * 1024,
) -> str:
    """
    Calcola l'hash SHA-256 di un file.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"File non trovato: {path}"
        )

    digest = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(chunk_size)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def get_git_commit(
    project_root: Path | None = None,
) -> str | None:
    """
    Restituisce l'hash breve del commit Git corrente.

    Se il progetto non è un repository Git o Git non
    è disponibile, restituisce None.
    """

    cwd = project_root or Path.cwd()

    try:
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "--short",
                "HEAD",
            ],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )

        commit = result.stdout.strip()

        return commit or None

    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
    ):
        return None


def get_git_status(
    project_root: Path | None = None,
) -> str:
    """
    Indica se il repository Git contiene modifiche
    non ancora registrate.
    """

    cwd = project_root or Path.cwd()

    try:
        result = subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
            ],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )

        return (
            "dirty"
            if result.stdout.strip()
            else "clean"
        )

    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
    ):
        return "unavailable"


def describe_file(
    path: Path,
) -> dict[str, Any]:
    """
    Costruisce i metadati tecnici di un file.
    """

    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "size_bytes": None,
            "sha256": None,
        }

    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": calculate_sha256(path),
    }


def describe_parquet(
    path: Path,
) -> dict[str, Any]:
    """
    Aggiunge ai metadati tecnici anche le informazioni
    strutturali di un file Parquet.
    """

    metadata = describe_file(path)

    if not path.exists():
        return metadata

    frame = pd.read_parquet(path)

    metadata.update(
        {
            "records": int(len(frame)),
            "columns": int(len(frame.columns)),
            "column_names": frame.columns.tolist(),
        }
    )

    return metadata


def build_dataset_manifest(
    *,
    dataset_path: Path,
    quality_report_path: Path,
    source_paths: list[Path],
    manifest_dir: Path,
    start_year: int,
    end_year: int,
    dataset_version: str,
    pipeline_version: str,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """
    Genera il manifest versionato del dataset One Health.
    """

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset finale non trovato: {dataset_path}"
        )

    if not quality_report_path.exists():
        raise FileNotFoundError(
            "Data Quality Report non trovato: "
            f"{quality_report_path}"
        )

    frame = pd.read_parquet(dataset_path)

    if frame.empty:
        raise ValueError(
            "Il dataset One Health è vuoto."
        )

    quality_report = json.loads(
        quality_report_path.read_text(
            encoding="utf-8"
        )
    )

    generated_at = datetime.now(
        timezone.utc
    )

    timestamp = generated_at.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    indicators = (
        sorted(
            frame["indicator_code"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if "indicator_code" in frame.columns
        else []
    )

    asl_values = (
        sorted(
            frame["asl"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if "asl" in frame.columns
        else []
    )

    years = (
        sorted(
            frame["year"]
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
        if "year" in frame.columns
        else []
    )

    source_files = [
        describe_file(path)
        for path in source_paths
    ]

    manifest: dict[str, Any] = {
        "manifest_type": "one_health_dataset_manifest",
        "dataset_name": "one_health_puglia",
        "dataset_version": dataset_version,
        "pipeline_version": pipeline_version,
        "generated_at_utc": generated_at.isoformat(),
        "period": {
            "start_year": start_year,
            "end_year": end_year,
            "actual_years": years,
        },
        "software": {
            "python_version": platform.python_version(),
            "python_implementation":
                platform.python_implementation(),
            "operating_system": platform.platform(),
            "git_commit": get_git_commit(project_root),
            "git_status": get_git_status(project_root),
        },
        "dataset": describe_parquet(
            dataset_path
        ),
        "dimensions": {
            "records": int(len(frame)),
            "columns": int(len(frame.columns)),
            "indicators": indicators,
            "asl": asl_values,
            "sexes": (
                sorted(
                    frame["sex"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )
                if "sex" in frame.columns
                else []
            ),
            "age_groups": (
                sorted(
                    frame["age_group"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )
                if "age_group" in frame.columns
                else []
            ),
        },
        "quality": {
            "status": quality_report.get(
                "status"
            ),
            "critical_issue_count":
                quality_report.get(
                    "critical_issue_count"
                ),
            "report_path":
                str(quality_report_path),
            "report_sha256":
                calculate_sha256(
                    quality_report_path
                ),
        },
        "source_files": source_files,
    }

    manifest_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    versioned_path = (
        manifest_dir
        / (
            "one_health_manifest_"
            f"{start_year}_{end_year}_"
            f"v{dataset_version}_"
            f"{timestamp}.json"
        )
    )

    latest_path = (
        manifest_dir
        / "latest_manifest.json"
    )

    manifest_text = json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
    )

    versioned_path.write_text(
        manifest_text,
        encoding="utf-8",
    )

    latest_path.write_text(
        manifest_text,
        encoding="utf-8",
    )

    print("=" * 70)
    print("DATASET MANIFEST")
    print("=" * 70)
    print("Dataset version:", dataset_version)
    print("Pipeline version:", pipeline_version)
    print(
        "Dataset SHA-256:",
        manifest["dataset"]["sha256"],
    )
    print(
        "Quality status:",
        manifest["quality"]["status"],
    )
    print(
        "Git commit:",
        manifest["software"]["git_commit"],
    )
    print(
        "Git status:",
        manifest["software"]["git_status"],
    )
    print("Manifest:", versioned_path)
    print("Manifest latest:", latest_path)

    return manifest