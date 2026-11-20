"""
OneHealthAI - Promotion Review v1.

Valuta la documentazione di una proposta di promozione.
Non modifica il registro e non concede accessi.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.one_health.artifact_access import load_registry


REQUIRED_EVIDENCE = (
    "source_metadata_verified",
    "methodology_verified",
    "data_quality_verified",
    "independent_validation_completed",
    "limitations_documented",
    "human_approval_recorded",
)


def review(artifact_id, evidence):
    registry = load_registry()

    matches = [
        a for a in registry["artifacts"]
        if a["id"] == artifact_id
    ]

    checks = {
        "registered": len(matches) == 1,
        "research_artifact": False,
        "approved_status": False,
    }

    if len(matches) == 1:
        artifact = matches[0]

        checks["research_artifact"] = (
            artifact.get("type") != "operational_dataset"
        )

        checks["approved_status"] = (
            artifact.get("status") == "approved"
        )

    for key in REQUIRED_EVIDENCE:
        checks[key] = evidence.get(key) is True

    eligible = all(checks.values())

    return {
        "schema_version": "1.0",
        "artifact_id": artifact_id,
        "reviewed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "checks": checks,
        "eligible_for_manual_promotion": eligible,
        "registry_modified": False,
        "master_access_granted": False,
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--artifact",
        required=True
    )

    parser.add_argument(
        "--evidence",
        type=Path
    )

    args = parser.parse_args()

    evidence = {}

    if args.evidence:
        evidence = json.loads(
            args.evidence.read_text(encoding="utf-8")
        )

    result = review(
        args.artifact,
        evidence
    )

    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False
    ))


if __name__ == "__main__":
    main()
