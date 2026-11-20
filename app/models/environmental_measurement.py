from datetime import date

from sqlalchemy import (
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EnvironmentalMeasurement(Base):
    __tablename__ = "environmental_measurement"

    __table_args__ = (
        UniqueConstraint(
            "station_id",
            "pollutant_id",
            "measurement_date",
            "network",
            name="uq_environmental_measurement",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    station_id: Mapped[int] = mapped_column(
        ForeignKey("monitoring_station.id"),
        nullable=False,
        index=True,
    )

    pollutant_id: Mapped[int] = mapped_column(
        ForeignKey("pollutant.id"),
        nullable=False,
        index=True,
    )

    measurement_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(50))

    network: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_limit: Mapped[float | None] = mapped_column(Float)

    source_exceedances_ytd: Mapped[int | None] = mapped_column(Integer)

    source_quality_index: Mapped[float | None] = mapped_column(Float)

    source_quality_class: Mapped[str | None] = mapped_column(String(50))

    quality_status: Mapped[str | None] = mapped_column(String(50))

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ARPAP",
    )