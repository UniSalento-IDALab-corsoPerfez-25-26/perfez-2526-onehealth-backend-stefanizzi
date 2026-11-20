from pathlib import Path

from etl.parsers.measurements import parse_measurements
from etl.validators.measurements import validate_measurements


def transform_measurements(
    source_path: Path,
    output_path: Path,
) -> None:
    frame = parse_measurements(source_path)
    frame = validate_measurements(frame)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    frame.to_parquet(
        output_path,
        index=False,
    )

    print(f"Record elaborati: {len(frame)}")
    print()
    print(frame["quality_status"].value_counts(dropna=False))
    print()
    print(f"File creato: {output_path}")