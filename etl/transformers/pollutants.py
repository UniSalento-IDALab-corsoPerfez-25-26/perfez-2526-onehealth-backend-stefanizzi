from pathlib import Path

from etl.parsers.pollutants import parse_pollutants
from etl.validators.pollutants import validate_pollutants


def transform_pollutants(
    source_path: Path,
    output_path: Path,
) -> None:

    frame = parse_pollutants(source_path)
    frame = validate_pollutants(frame)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame.to_parquet(
        output_path,
        index=False,
    )

    print(f"Inquinanti elaborati: {len(frame)}")
    print()
    print(
        frame["quality_status"]
        .value_counts(dropna=False)
    )
    print()
    print(f"File creato: {output_path}")