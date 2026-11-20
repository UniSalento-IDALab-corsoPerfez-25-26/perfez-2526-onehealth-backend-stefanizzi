from pathlib import Path

from etl.parsers.stations import parse_stations
from etl.validators.stations import validate_stations


def transform_stations(
    source_path: Path,
    output_path: Path,
) -> None:
    frame = parse_stations(source_path)
    frame = validate_stations(frame)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame.to_parquet(
        output_path,
        index=False,
    )

    print(f"Stazioni elaborate: {len(frame)}")
    print()
    print(
        frame["quality_status"]
        .value_counts(dropna=False)
    )
    print()
    print(f"File creato: {output_path}")