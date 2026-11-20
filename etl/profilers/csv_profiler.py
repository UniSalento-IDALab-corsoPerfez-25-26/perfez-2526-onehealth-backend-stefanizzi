from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd


@dataclass
class CsvProfile:
    path: str
    rows: int
    columns: int
    column_names: list[str]
    dtypes: dict[str, str]
    nulls: dict[str, int]
    duplicate_rows: int
    sample_distinct_values: dict[str, list[str]]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def read_arpa_csv(path: Path) -> pd.DataFrame:
    attempts = [
        {"sep": ";", "encoding": "utf-8-sig"},
        {"sep": ",", "encoding": "utf-8-sig"},
        {"sep": ";", "encoding": "latin-1"},
        {"sep": ",", "encoding": "latin-1"},
    ]
    last_error: Exception | None = None
    for options in attempts:
        try:
            frame = pd.read_csv(path, **options)
            if len(frame.columns) > 1:
                frame.columns = [str(column).strip() for column in frame.columns]
                return frame
        except Exception as exc:  # pragma: no cover - fallback diagnostico
            last_error = exc
    raise ValueError(f"Impossibile interpretare il CSV ARPA: {path}") from last_error


def profile_csv(path: Path) -> CsvProfile:
    frame = read_arpa_csv(path)
    distinct: dict[str, list[str]] = {}
    for column in frame.columns:
        values = frame[column].dropna().astype(str).drop_duplicates().head(10).tolist()
        distinct[str(column)] = values

    return CsvProfile(
        path=str(path),
        rows=len(frame),
        columns=len(frame.columns),
        column_names=[str(column) for column in frame.columns],
        dtypes={str(column): str(dtype) for column, dtype in frame.dtypes.items()},
        nulls={str(column): int(value) for column, value in frame.isna().sum().items()},
        duplicate_rows=int(frame.duplicated().sum()),
        sample_distinct_values=distinct,
    )
