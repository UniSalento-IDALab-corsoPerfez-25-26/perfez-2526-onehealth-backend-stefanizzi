from typing import Literal

from pydantic import BaseModel


class EnvironmentExposureUpdatedData(
    BaseModel
):
    start_year: int
    end_year: int

    pollutants: list[str]

    geographic_level: Literal[
        "STATION",
        "MUNICIPALITY",
        "ASL",
        "REGION",
    ]

    dataset_uri: str

    dataset_sha256: str

    record_count: int

    quality_status: Literal[
        "PASS",
        "WARNING",
        "FAIL",
    ]