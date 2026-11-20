from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issue"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_run.id"),
        nullable=False,
        index=True,
    )

    issue_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    source_station_id: Mapped[str | None] = mapped_column(
        String(50)
    )

    pollutant_code: Mapped[str | None] = mapped_column(
        String(30)
    )

    measurement_date: Mapped[str | None] = mapped_column(
        String(20)
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )