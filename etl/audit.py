from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import IngestionRun


def start_ingestion_run(
    session: Session,
    *,
    mode: str,
    dataset_type: str,
    file_path: str | None = None,
) -> IngestionRun:
    run = IngestionRun(
        source="ARPAP",
        mode=mode,
        dataset_type=dataset_type,
        file_path=file_path,
        started_at=datetime.now(timezone.utc),
        status="RUNNING",
    )

    session.add(run)
    session.commit()
    session.refresh(run)

    return run


def complete_ingestion_run(
    session: Session,
    run: IngestionRun,
    *,
    input_records: int,
    inserted_records: int,
    updated_records: int,
    skipped_records: int,
    warning_records: int,
    duplicate_records: int,
) -> None:
    run.completed_at = datetime.now(timezone.utc)
    run.status = "COMPLETED"

    run.input_records = input_records
    run.inserted_records = inserted_records
    run.updated_records = updated_records
    run.skipped_records = skipped_records
    run.warning_records = warning_records
    run.duplicate_records = duplicate_records

    session.commit()


def fail_ingestion_run(
    session: Session,
    run: IngestionRun,
    error: Exception,
) -> None:
    run.completed_at = datetime.now(timezone.utc)
    run.status = "FAILED"
    run.error_message = str(error)

    session.commit()