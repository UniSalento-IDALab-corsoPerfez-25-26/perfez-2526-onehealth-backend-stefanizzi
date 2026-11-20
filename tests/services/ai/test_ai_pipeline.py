import pandas as pd

from services.ai.app.service import (
    AIService,
)


def test_priority_dataset_bpco_2023():
    service = AIService()

    frame = (
        service.build_priority_dataset(
            indicator_code="BPCO",
            year=2023,
        )
    )

    assert not frame.empty

    assert len(frame) == 6

    assert (
        frame["indicator_code"]
        == "BPCO"
    ).all()

    assert (
        frame["year"]
        == 2023
    ).all()

    assert sorted(
        frame["asl"].tolist()
    ) == [
        "BAT",
        "Bari",
        "Brindisi",
        "Foggia",
        "Lecce",
        "Taranto",
    ]


def test_priority_dataset_has_no_pseudoreplication():
    service = AIService()

    frame = (
        service.build_priority_dataset(
            indicator_code="BPCO",
            year=2023,
        )
    )

    duplicates = frame.duplicated(
        subset=[
            "indicator_code",
            "year",
            "asl",
        ]
    ).sum()

    assert duplicates == 0


def test_priority_score_is_reproducible():
    service = AIService()

    frame = (
        service.build_priority_dataset(
            indicator_code="BPCO",
            year=2023,
        )
    )

    scores = {
        row["asl"]:
            float(
                row["priority_score"]
            )
        for _, row
        in frame.iterrows()
    }

    assert scores == {
        "Brindisi": 81.25,
        "Taranto": 77.08,
        "Bari": 64.58,
        "BAT": 62.50,
        "Lecce": 45.83,
        "Foggia": 18.75,
    }


def test_priority_ranking_is_reproducible():
    service = AIService()

    frame = (
        service.build_priority_dataset(
            indicator_code="BPCO",
            year=2023,
        )
    )

    assert frame[
        "asl"
    ].tolist() == [
        "Brindisi",
        "Taranto",
        "Bari",
        "BAT",
        "Lecce",
        "Foggia",
    ]

    assert (
        frame[
            "priority_rank"
        ]
        .astype(int)
        .tolist()
        == [
            1,
            2,
            3,
            4,
            5,
            6,
        ]
    )


def test_priority_score_formula_lecce():
    service = AIService()

    frame = (
        service.build_priority_dataset(
            indicator_code="BPCO",
            year=2023,
        )
    )

    lecce = frame[
        frame["asl"] == "Lecce"
    ].iloc[0]

    expected_score = (
        (
            0.5
            * float(
                lecce[
                    "health_percentile"
                ]
            )
        )
        +
        (
            0.5
            * float(
                lecce[
                    "environment_percentile"
                ]
            )
        )
    ) * 100

    assert round(
        expected_score,
        2,
    ) == 45.83

    assert (
        float(
            lecce["priority_score"]
        )
        == 45.83
    )


def test_missing_meteorology_does_not_zero_priority():
    service = AIService()

    frame = (
        service.build_priority_dataset(
            indicator_code="BPCO",
            year=2023,
        )
    )

    bat = frame[
        frame["asl"] == "BAT"
    ].iloc[0]

    assert (
        float(
            bat["priority_score"]
        )
        == 62.50
    )

    assert (
        bat[
            "integration_quality_status"
        ]
        == "VALID_WITHOUT_METEO"
    )

    assert pd.isna(
        bat[
            "meteo_quality_status"
        ]
    )

    assert not bool(
        bat[
            "meteo_available"
        ]
    )

    assert pd.isna(
        bat[
            "meteo_year_coverage_percent"
        ]
    )


def test_health_and_environment_are_separate_components():
    service = AIService()

    frame = (
        service.build_priority_dataset(
            indicator_code="BPCO",
            year=2023,
        )
    )

    taranto = frame[
        frame["asl"] == "Taranto"
    ].iloc[0]

    brindisi = frame[
        frame["asl"] == "Brindisi"
    ].iloc[0]

    # Taranto has the highest health burden.
    assert (
        float(
            taranto[
                "health_percentile"
            ]
        )
        == 1.0
    )

    # Brindisi ranks first overall because the
    # environmental component is higher.
    assert (
        float(
            brindisi[
                "priority_score"
            ]
        )
        >
        float(
            taranto[
                "priority_score"
            ]
        )
    )

    assert (
        float(
            brindisi[
                "environment_percentile"
            ]
        )
        >
        float(
            taranto[
                "environment_percentile"
            ]
        )
    )


def test_unknown_indicator_returns_empty_dataset():
    service = AIService()

    frame = (
        service.build_priority_dataset(
            indicator_code=
                "UNKNOWN_INDICATOR",
            year=2023,
        )
    )

    assert frame.empty


def test_unknown_year_returns_empty_dataset():
    service = AIService()

    frame = (
        service.build_priority_dataset(
            indicator_code="BPCO",
            year=1900,
        )
    )

    assert frame.empty