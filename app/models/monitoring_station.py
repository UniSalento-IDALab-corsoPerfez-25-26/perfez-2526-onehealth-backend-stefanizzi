from geoalchemy2 import Geometry
from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MonitoringStation(Base):
    __tablename__ = "monitoring_station"

    id: Mapped[int] = mapped_column(primary_key=True)

    source_station_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    municipality: Mapped[str | None] = mapped_column(String(150))
    province: Mapped[str | None] = mapped_column(String(100), index=True)
    network: Mapped[str | None] = mapped_column(String(50))
    network_interest: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(255))

    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)

    geometry = mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=4326,
        )
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ARPAP",
    )