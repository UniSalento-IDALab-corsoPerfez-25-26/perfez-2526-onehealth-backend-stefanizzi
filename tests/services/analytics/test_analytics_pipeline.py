from services.analytics.app.service import (
    AnalyticsService,
)


def test_analytical_dataset_bpco():
    service = AnalyticsService()

    frame = (
        service.build_analytical_dataset(
            indicator_code="BPCO"
        )
    )

    assert not frame.empty

    assert len(frame) == 18

    assert (
        sorted(
            frame["year"]
            .unique()
            .tolist()
        )
        == [
            2021,
            2022,
            2023,
        ]
    )

    assert (
        sorted(
            frame["asl"]
            .unique()
            .tolist()
        )
        == [
            "BAT",
            "Bari",
            "Brindisi",
            "Foggia",
            "Lecce",
            "Taranto",
        ]
    )

    duplicates = frame.duplicated(
        subset=[
            "indicator_code",
            "year",
            "asl",
        ]
    ).sum()

    assert duplicates == 0

    assert (
        frame["indicator_code"]
        == "BPCO"
    ).all()

    assert (
        frame[
            "prevalence_per_1000"
        ]
        .notna()
        .all()
    )


def test_analytical_dataset_preserves_environment():
    service = AnalyticsService()

    frame = (
        service.build_analytical_dataset(
            indicator_code="BPCO"
        )
    )

    environmental_columns = [
        "no2_mean_value",
        "o3_mean_value",
        "pm10_mean_value",
        "pm2_5_mean_value",
    ]

    for column in environmental_columns:
        assert column in frame.columns
        assert frame[column].notna().all()


def test_analytical_dataset_lecce_2023():
    service = AnalyticsService()

    frame = (
        service.build_analytical_dataset(
            indicator_code="BPCO"
        )
    )

    row = frame[
        (
            frame["year"]
            == 2023
        )
        & (
            frame["asl"]
            == "Lecce"
        )
    ]

    assert len(row) == 1

    record = row.iloc[0]

    assert record["cases"] == 31688
    assert (
        record["population"]
        == 482772
    )

    assert round(
        float(
            record[
                "prevalence_per_1000"
            ]
        ),
        4,
    ) == 65.6376

    assert round(
        float(
            record[
                "no2_mean_value"
            ]
        ),
        4,
    ) == 25.8291

    assert round(
        float(
            record[
                "o3_mean_value"
            ]
        ),
        4,
    ) == 88.8756

    assert round(
        float(
            record[
                "pm10_mean_value"
            ]
        ),
        4,
    ) == 22.3395

    assert round(
        float(
            record[
                "pm2_5_mean_value"
            ]
        ),
        4,
    ) == 12.9094