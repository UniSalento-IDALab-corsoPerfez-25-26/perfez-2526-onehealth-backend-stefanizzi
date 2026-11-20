"""
OneHealthAI - Promotion Audit v1.

Registra richieste di promozione senza modificare
le autorizzazioni degli artefatti.
"""

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from scripts.one_health.promotion_review import review


AUDIT_PATH = Path(
    "data/reports/one_health/"
    "promotion_audit_v1.jsonl"
)


def record_request(artifact_id, evidence=None):
    result = review(
        artifact_id,
        evidence or {}
    )

    status = (
        "REVIEW_REQUIRED"
        if result["eligible_for_manual_promotion"]
        else "BLOCKED"
    )

    entry = {
        "request_id": str(uuid.uuid4()),
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "artifact_id": artifact_id,
        "status": status,
        "review": result,
        "decision": None,
        "approved_by": None,
        "master_access_granted": False,
    }

    AUDIT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with AUDIT_PATH.open(
        "a",
        encoding="utf-8"
    ) as file:
        file.write(
            json.dumps(
                entry,
                ensure_ascii=False
            ) + "\n"
        )

    return entry


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

    entry = record_request(
        args.artifact,
        evidence
    )

    print(json.dumps(
        entry,
        indent=2,
        ensure_ascii=False
    ))


if __name__ == "__main__":
    main()
