import json
from datetime import date, datetime
from pathlib import Path

REPORT = Path(
    "data/processed/one_health/operational/source_status.json"
)

def plan_updates(report):
    sources = report["sources"]
    today = date.today()
    actions = []

    arpa = sources["environment"].get("operational_database", {})
    last_date = arpa.get("last_date")

    if arpa.get("status") != "READY" or not last_date:
        environment_status = "CHECK_REQUIRED"
        reason = "Database operativo non disponibile"
    else:
        days = (today - date.fromisoformat(last_date)).days
        environment_status = (
            "CHECK_FOR_UPDATES" if days > 7 else "CURRENT"
        )
        reason = f"Ultima misurazione: {last_date}; {days} giorni fa"

    actions.append({
        "domain": "environment",
        "status": environment_status,
        "reason": reason,
        "automatic_ingestion": False
    })

    meteo = sources["meteorology"]["datasets"]
    partial_2026 = any(
        item.get("last_year") == 2026
        and "partial" in item["file"].lower()
        and item["status"] == "READABLE"
        for item in meteo
    )

    meteo_path = Path(
        "data/processed/meteorology/meteorology_asl_2026_partial.parquet"
    )

    meteo_end = None

    if partial_2026 and meteo_path.is_file():
        import pandas as pd

        df = pd.read_parquet(meteo_path)
        if (
            len(df) == 6
            and "period_end" in df.columns
            and df["period_end"].notna().all()
        ):
            dates = pd.to_datetime(df["period_end"], errors="coerce")
            if dates.notna().all() and dates.nunique() == 1:
                meteo_end = dates.iloc[0].date()

    if meteo_end is None:
        meteo_status = "CHECK_REQUIRED"
        meteo_reason = "Copertura temporale meteorologica da verificare"
    else:
        days = (today - meteo_end).days
        meteo_status = (
            "CURRENT" if 0 <= days <= 7
            else "CHECK_FOR_UPDATES"
        )
        meteo_reason = (
            f"Ultima osservazione: {meteo_end.isoformat()}; "
            f"{days} giorni fa; anno 2026 provvisorio"
        )

    actions.append({
        "domain": "meteorology",
        "status": meteo_status,
        "reason": meteo_reason,
        "automatic_ingestion": False
    })

    for domain in ("health", "demography"):
        datasets = sources[domain]["datasets"]
        years = [
            item["last_year"]
            for item in datasets
            if item["status"] == "READABLE"
            and item.get("last_year") is not None
        ]
        latest = max(years) if years else None

        actions.append({
            "domain": domain,
            "status": "CHECK_OFFICIAL_RELEASE",
            "reason": (
                f"Ultimo anno locale: {latest}; "
                "verificare nuove pubblicazioni ISTAT"
            ),
            "automatic_ingestion": False
        })

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "mode": "PLAN_ONLY",
        "actions": actions
    }

if __name__ == "__main__":
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    plan = plan_updates(report)

    output = Path(
        "data/processed/one_health/operational/update_plan.json"
    )
    output.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    print("\nONEHEALTHAI — PIANO AGGIORNAMENTI")
    for action in plan["actions"]:
        print(
            f"{action['domain']}: {action['status']}\n"
            f"  {action['reason']}"
        )
    print("\nAcquisizioni automatiche: DISABILITATE")
    print("Piano salvato:", output)
