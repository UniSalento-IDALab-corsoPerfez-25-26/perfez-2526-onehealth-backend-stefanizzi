from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Pollutant(Base):
    __tablename__ = "pollutant"

    id: Mapped[int] = mapped_column(primary_key=True)

    source_pollutant_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(Text)
    measurement_period: Mapped[str | None] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(50))

    source_limit: Mapped[float | None] = mapped_column(Float)
    alert_threshold: Mapped[float | None] = mapped_column(Float)

    eionet_uri: Mapped[str | None] = mapped_column(String(500))

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ARPAP",
    )