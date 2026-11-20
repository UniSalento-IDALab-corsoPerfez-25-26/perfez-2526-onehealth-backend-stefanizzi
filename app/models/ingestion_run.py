from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_run"

    id: Mapped[int] = mapped_column(primary_key=True)

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ARPAP",
    )

    mode: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    dataset_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    file_path: Mapped[str | None] = mapped_column(
        Text
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    input_records: Mapped[int | None] = mapped_column(
        Integer
    )

    inserted_records: Mapped[int | None] = mapped_column(
        Integer
    )

    updated_records: Mapped[int | None] = mapped_column(
        Integer
    )

    skipped_records: Mapped[int | None] = mapped_column(
        Integer
    )

    warning_records: Mapped[int | None] = mapped_column(
        Integer
    )

    duplicate_records: Mapped[int | None] = mapped_column(
        Integer
    )

    error_message: Mapped[str | None] = mapped_column(
        Text
    )