from datetime import date

import pytest

from etl.models.arpa import ArpaMeasurementQuery, IngestionMode


def test_daily_query_uses_italian_date_format() -> None:
    query = ArpaMeasurementQuery(
        mode=IngestionMode.DAILY,
        measurement_date=date(2026, 7, 21),
        pollutant_label="PM10",
    )
    assert query.to_params()["measurement_date"] == "21/07/2026"
    assert query.to_params()["label_pollutant"] == "PM10"


def test_backfill_requires_year() -> None:
    with pytest.raises(ValueError):
        ArpaMeasurementQuery(mode=IngestionMode.BACKFILL)
