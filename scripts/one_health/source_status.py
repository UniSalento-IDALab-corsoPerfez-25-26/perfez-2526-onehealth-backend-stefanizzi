import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

ROOT = Path("data/processed")
REGISTRY = Path("config/one_health/source_registry_v1.json")

PATTERNS = {
    "environment": [
        "one_health/research/environmental_exposure_2010_2025_QC_v1.parquet"
    ],
    "meteorology": [
        "meteorology/meteorology_asl_historical_2010_2025.parquet",
        "meteorology/meteorology_asl_2026_partial.parquet"
    ],
    "health": [
        "one_health/research/consolidated_qc_v1/ml_hfa_hospital_CONSOLIDATED_QC_v1.parquet",
        "one_health/research/consolidated_qc_v1/ml_hfa_mortality_CONSOLIDATED_QC_v1.parquet"
    ],
    "demography": [
        "demography/population_asl_historical_2006_2023.parquet",
        "demography/population_asl_2024_2026.parquet"
    ]
}

def inspect_file(path):
    if not path.exists():
        return {"file": str(path), "status": "MISSING"}

    try:
        df = pd.read_parquet(path)
        years = (
            sorted(df["year"].dropna().astype(int).unique().tolist())
            if "year" in df.columns else []
        )
        quality = {}
        for col in ("quality_status", "meteo_quality_status"):
            if col in df.columns:
                quality = {
                    str(k): int(v)
                    for k, v in df[col].value_counts(dropna=False).items()
                }
                break

        return {
            "file": str(path),
            "status": "READABLE",
            "records": len(df),
            "first_year": years[0] if years else None,
            "last_year": years[-1] if years else None,
            "quality": quality
        }
    except Exception as exc:
        return {
            "file": str(path),
            "status": "ERROR",
            "error": str(exc)
        }

def main():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {}
    }

    for domain, config in registry["sources"].items():
        files = [inspect_file(ROOT / p) for p in PATTERNS[domain]]
        report["sources"][domain] = {
            "provider": config["provider"],
            "update_policy": config["update_policy"],
            "datasets": files,
            "status": (
                "NOT_CONFIGURED" if not files
                else "READY" if all(f["status"] == "READABLE" for f in files)
                else "CHECK_REQUIRED"
            )
        }


    # ONEHEALTHAI_LIVE_DATABASE_STATUS_V1
    try:
        from sqlalchemy import func
        from app.core.database import SessionLocal
        from app.models import EnvironmentalMeasurement

        with SessionLocal() as db:
            count, first_date, last_date = db.query(
                func.count(EnvironmentalMeasurement.id),
                func.min(EnvironmentalMeasurement.measurement_date),
                func.max(EnvironmentalMeasurement.measurement_date),
            ).one()

        report["sources"]["environment"]["operational_database"] = {
            "source": "PostgreSQL",
            "dataset": "environmental_measurements",
            "status": "READY" if count else "EMPTY",
            "records": int(count),
            "first_date": str(first_date) if first_date else None,
            "last_date": str(last_date) if last_date else None,
        }
    except Exception as exc:
        report["sources"]["environment"]["operational_database"] = {
            "source": "PostgreSQL",
            "status": "ERROR",
            "error": str(exc),
        }

    output = Path("data/processed/one_health/operational/source_status.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\nONEHEALTHAI — STATO DELLE FONTI")
    for domain, info in report["sources"].items():
        print(f"\n{domain.upper()}: {info['status']}")
        for dataset in info["datasets"]:
            print(
                f"  {Path(dataset['file']).name}: "
                f"{dataset['status']} | "
                f"{dataset.get('first_year')}–{dataset.get('last_year')} | "
                f"{dataset.get('records', 0)} record"
            )
    print(f"\nReport salvato: {output}")

if __name__ == "__main__":
    main()
