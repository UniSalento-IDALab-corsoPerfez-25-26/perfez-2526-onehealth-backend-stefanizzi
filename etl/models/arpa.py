from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class IngestionMode(StrEnum):
    DAILY = "daily"
    BACKFILL = "backfill"


class OutputFormat(StrEnum):
    CSV = "CSV"
    GEOJSON = "GeoJSON"


class ArpaMeasurementQuery(BaseModel):
    mode: IngestionMode
    year: int | None = Field(default=None, ge=2021)
    month: int | None = Field(default=None, ge=1, le=12)
    measurement_date: date | None = None
    network: str = "RRQA"
    station_id: str | None = None
    pollutant_id: str | None = None
    pollutant_label: str | None = None
    output_format: OutputFormat = OutputFormat.CSV

    @model_validator(mode="after")
    def validate_mode(self) -> "ArpaMeasurementQuery":
        if self.mode == IngestionMode.BACKFILL and self.year is None:
            raise ValueError("BACKFILL richiede almeno l'anno")
        if self.measurement_date and (self.year or self.month):
            raise ValueError("measurement_date non può essere combinata con year/month")
        return self

    def to_params(self) -> dict[str, str | int]:
        params: dict[str, str | int] = {
            "format": self.output_format.value,
            "network": self.network,
        }
        if self.year is not None:
            params["year"] = self.year
        if self.month is not None:
            params["month"] = self.month
        if self.measurement_date is not None:
            params["measurement_date"] = self.measurement_date.strftime("%d/%m/%Y")
        if self.station_id:
            params["id_station"] = self.station_id
        if self.pollutant_id:
            params["id_pollutant"] = self.pollutant_id
        if self.pollutant_label:
            params["label_pollutant"] = self.pollutant_label
        return params
