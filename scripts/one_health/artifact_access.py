from pathlib import Path
import argparse
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REGISTRY = (
    PROJECT_ROOT
    / "config/one_health/artifact_governance_v1.json"
)


class AccessDenied(Exception):
    pass


def load_registry():
    with REGISTRY.open(encoding="utf-8") as f:
        registry = json.load(f)

    policy = registry.get("policy", {})

    if (
        policy.get("default_access") != "research_only"
        or policy.get("automatic_promotion_allowed") is not False
        or policy.get("master_dss_requires_explicit_approval") is not True
        or policy.get("missing_artifact_policy") != "deny"
        or policy.get("unregistered_artifact_policy") != "deny"
    ):
        raise AccessDenied("Policy di governance non valida")

    return registry


def resolve_artifact(artifact_id, consumer):
    if consumer not in ("research", "master"):
        raise AccessDenied("Consumer non riconosciuto")

    registry = load_registry()

    matches = [
        a for a in registry["artifacts"]
        if a.get("id") == artifact_id
    ]

    if len(matches) != 1:
        raise AccessDenied(
            "Artefatto assente o identificativo duplicato"
        )

    artifact = matches[0]

    if consumer == "master":
        if (
            artifact.get("master_dss_approved") is not True
            or artifact.get("status") != "approved"
        ):
            raise AccessDenied(
                "Artefatto non approvato per Master DSS"
            )

    relative_path = Path(artifact["path"])

    if relative_path.is_absolute():
        raise AccessDenied("Percorso assoluto non consentito")

    resolved = (PROJECT_ROOT / relative_path).resolve()

    if not resolved.is_relative_to(PROJECT_ROOT):
        raise AccessDenied("Percorso esterno al progetto")

    if not resolved.is_file():
        raise AccessDenied("Artefatto non disponibile")

    return resolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--consumer",
        choices=["research", "master"],
        required=True
    )
    parser.add_argument("--artifact", required=True)

    args = parser.parse_args()

    try:
        path = resolve_artifact(
            args.artifact,
            args.consumer
        )
        print(f"ACCESS GRANTED: {path}")

    except (
        AccessDenied,
        OSError,
        KeyError,
        TypeError,
        ValueError
    ) as exc:
        print(f"ACCESS DENIED: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
