import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

STEPS = [
    "source_status.py",
    "update_plan.py",
    "pending_updates.py",
]

def main():
    print("ONEHEALTHAI — COORDINAMENTO AGGIORNAMENTI", flush=True)

    for script in STEPS:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/one_health" / script)],
            cwd=ROOT,
            check=False,
        )
        if result.returncode != 0:
            print(f"ERRORE: {script} — coordinamento interrotto")
            return result.returncode

    path = ROOT / "data/processed/one_health/operational/pending_updates.json"
    pending = json.loads(path.read_text(encoding="utf-8"))

    print("\nRIEPILOGO")
    print("Operazioni pendenti:", len(pending["tasks"]))
    print("Acquisizioni eseguite: 0")
    print("Promozioni scientifiche eseguite: 0")
    return 0

if __name__ == "__main__":
    sys.exit(main())
