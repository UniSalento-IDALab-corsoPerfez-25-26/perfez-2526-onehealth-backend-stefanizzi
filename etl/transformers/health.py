from pathlib import Path

import pandas as pd

from etl.parsers.health import parse_bpco
from etl.validators.health import (
    validate_health_indicators,
)

from etl.parsers.health import (
    parse_bpco,
    parse_chronic_indicator,
)

def transform_bpco(
    source_paths: list[Path],
    output_path: Path,
) -> None:

    frames = []

    for source_path in source_paths:
        frame = parse_bpco(source_path)
        frames.append(frame)

    combined = pd.concat(
        frames,
        ignore_index=True,
    )

    combined = validate_health_indicators(
        combined
    )

    combined = combined.sort_values(
        [
            "year",
            "geographic_level",
            "geographic_area",
            "sex",
            "age_group",
        ]
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_parquet(
        output_path,
        index=False,
    )

    print(
        f"Record sanitari elaborati: {len(combined)}"
    )

    print()
    print(
        combined["quality_status"]
        .value_counts(dropna=False)
    )

    print()
    print(
        f"File creato: {output_path}"
    )

def transform_chronic_indicator(
    source_paths: list[Path],
    output_path: Path,
    *,
    indicator_code: str,
    indicator_name: str,
) -> None:

    frames = []

    for source_path in source_paths:
        frame = parse_chronic_indicator(
            source_path,
            indicator_code=indicator_code,
            indicator_name=indicator_name,
        )
        frames.append(frame)

    combined = pd.concat(
        frames,
        ignore_index=True,
    )

    combined = validate_health_indicators(
        combined
    )

    combined = combined.sort_values(
        [
            "year",
            "geographic_level",
            "geographic_area",
            "sex",
            "age_group",
        ]
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_parquet(
        output_path,
        index=False,
    )

    print(f"Indicatore: {indicator_code}")
    print(f"Record elaborati: {len(combined)}")
    print()
    print(
        combined["quality_status"]
        .value_counts(dropna=False)
    )
    print()
    print(f"File creato: {output_path}")