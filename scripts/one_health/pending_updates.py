import json
from datetime import datetime
from pathlib import Path

ROOT = Path("data/processed/one_health/operational")
PLAN = ROOT / "update_plan.json"
OUTPUT = ROOT / "pending_updates.json"

ELIGIBLE = {
    "environment": "CHECK_FOR_UPDATES",
    "meteorology": "CHECK_FOR_UPDATES",
}

def build_pending_updates(plan):
    tasks = []

    for action in plan.get("actions", []):
        domain = action.get("domain")
        status = action.get("status")

        if ELIGIBLE.get(domain) == status:
            tasks.append({
                "domain": domain,
                "operation": "INCREMENTAL_UPDATE",
                "execution": "REQUIRES_EXPLICIT_APPROVAL",
                "status": "PENDING",
            })

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "mode": "DRY_RUN",
        "automatic_ingestion": False,
        "tasks": tasks,
    }

if __name__ == "__main__":
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    result = build_pending_updates(plan)

    OUTPUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("ONEHEALTHAI — AGGIORNAMENTI PENDENTI")
    print("Operazioni previste:", len(result["tasks"]))
    print("Acquisizioni eseguite: 0")
    print("Report:", OUTPUT)
