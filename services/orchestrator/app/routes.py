from fastapi import (
    APIRouter,
    Query,
)
from fastapi.responses import (
    JSONResponse,
)

from services.orchestrator.app.service import (
    OrchestratorService,
)


router = APIRouter()

orchestrator_service = (
    OrchestratorService()
)


@router.get("/workflow/plan")
def get_workflow_plan():
    return (
        orchestrator_service
        .get_workflow_plan()
    )


@router.post("/workflow/run")
async def run_workflow(
    meteorology_year: int = Query(
        default=2023,
        ge=2000,
    ),
    start_year: int = Query(
        default=2021,
        ge=2000,
    ),
    end_year: int = Query(
        default=2023,
        ge=2000,
    ),
):
    if start_year > end_year:
        return JSONResponse(
            status_code=400,
            content={
                "status": "INVALID_REQUEST",
                "detail": (
                    "start_year must be less "
                    "than or equal to end_year."
                ),
            },
        )

    result = (
        await orchestrator_service
        .run_workflow(
            meteorology_year=
                meteorology_year,
            start_year=
                start_year,
            end_year=
                end_year,
        )
    )

    if result["status"] == "FAILED":
        return JSONResponse(
            status_code=502,
            content=result,
        )

    return result


# ONEHEALTHAI_SOURCE_STATUS_API_V1
@router.get("/sources/status")
def get_source_status():
    """Restituisce lo stato delle fonti senza eseguire ingestion."""
    import json
    from pathlib import Path
    from fastapi import HTTPException

    report_path = Path(
        "data/processed/one_health/operational/source_status.json"
    )

    if not report_path.is_file():
        raise HTTPException(
            status_code=503,
            detail="Report delle fonti non disponibile"
        )

    try:
        report = json.loads(
            report_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Report non leggibile: {exc}"
        )

    return {
        "status": "OK",
        "mode": "CHECK_ONLY",
        "generated_at": report.get("generated_at"),
        "sources": report.get("sources", {}),
    }


# ONEHEALTHAI_UPDATE_PLAN_API_V1
@router.get("/sources/update-plan")
def get_source_update_plan():
    """Legge il piano di aggiornamento senza eseguire acquisizioni."""
    import json
    from pathlib import Path
    from fastapi import HTTPException

    path = Path(
        "data/processed/one_health/operational/update_plan.json"
    )

    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail="Piano aggiornamenti non disponibile"
        )

    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(
            status_code=503,
            detail="Piano aggiornamenti non leggibile"
        )

    return plan


# ONEHEALTHAI_COORDINATE_API_V1
@router.post("/sources/coordinate")
def coordinate_sources():
    import subprocess
    import sys
    import json
    from pathlib import Path
    from fastapi import HTTPException

    root = Path("/app")
    script = root / "scripts/one_health/coordinate_updates.py"

    if not script.is_file():
        raise HTTPException(
            status_code=503,
            detail="Coordinatore non disponibile nel container"
        )

    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Timeout del coordinatore"
        )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=result.stderr[-1000:] or result.stdout[-1000:]
        )

    report = root / "data/processed/one_health/operational/pending_updates.json"

    return {
        "status": "OK",
        "mode": "DRY_RUN",
        "result": json.loads(report.read_text(encoding="utf-8"))
    }
