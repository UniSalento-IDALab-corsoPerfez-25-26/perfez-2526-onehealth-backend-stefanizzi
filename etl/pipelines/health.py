from pathlib import Path

from etl.transformers.health import (
    transform_chronic_indicator,
)


HEALTH_INDICATORS = {
    "BPCO": {
        "indicator_name": "Broncopneumopatia cronica ostruttiva",
        "output_name": "bpco_2020_2023.parquet",
    },
    "DIABETES": {
        "indicator_name": "Diabete",
        "output_name": "diabetes_2020_2023.parquet",
    },
    "HYPERTENSION": {
        "indicator_name": "Ipertensione",
        "output_name": "hypertension_2020_2023.parquet",
    },
    "HEART_FAILURE": {
        "indicator_name": "Scompenso cardiaco",
        "output_name": "heart_failure_2020_2023.parquet",
    },
}


HISTORICAL_HEALTH_ASL_OUTPUT = Path(
    "data/processed/health/"
    "health_indicators_historical_asl.parquet"
)

def run_health_indicator_pipeline(
    *,
    source_paths: list[Path],
    indicator_code: str,
    output_dir: Path = Path(
        "data/processed/health"
    ),
) -> Path:
    """
    Esegue parsing, validazione e trasformazione
    di un indicatore sanitario.

    Utilizza esclusivamente la logica ETL esistente.
    """

    if indicator_code not in HEALTH_INDICATORS:
        raise ValueError(
            f"Indicatore sanitario non supportato: "
            f"{indicator_code}"
        )

    config = HEALTH_INDICATORS[
        indicator_code
    ]

    output_path = (
        output_dir
        / config["output_name"]
    )

    transform_chronic_indicator(
        source_paths=source_paths,
        output_path=output_path,
        indicator_code=indicator_code,
        indicator_name=(
            config["indicator_name"]
        ),
    )

    return output_path

import pandas as pd


def combine_health_indicators(
    *,
    input_paths: list[Path],
    output_path: Path = Path(
        "data/processed/health/"
        "health_indicators_2020_2023.parquet"
    ),
) -> Path:

    frames = []

    for path in input_paths:
        if not path.exists():
            raise FileNotFoundError(
                f"Dataset sanitario non trovato: "
                f"{path}"
            )

        frame = pd.read_parquet(path)

        frames.append(frame)

    if not frames:
        raise ValueError(
            "Nessun dataset sanitario da combinare."
        )

    combined = pd.concat(
        frames,
        ignore_index=True,
    )

    duplicate_key = [
        "indicator_code",
        "year",
        "geographic_level",
        "geographic_area",
        "sex",
        "age_group",
    ]

    duplicates = combined.duplicated(
        subset=duplicate_key,
        keep=False,
    )

    if duplicates.any():
        raise ValueError(
            "Trovati duplicati logici nel "
            "dataset sanitario combinato."
        )

    combined = combined.sort_values(
        duplicate_key
    ).reset_index(
        drop=True
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_parquet(
        output_path,
        index=False,
    )

    return output_path

from pathlib import Path

import pandas as pd


HISTORICAL_HEALTH_SOURCES = {
    "DIABETES": {
        "indicator_name": "Diabetes",
        "files": [
            Path("data/raw/health/diabetes_2006_2019.csv"),
            Path("data/raw/health/diabetes_2020_2022.csv"),
            Path("data/raw/health/diabetes_2023.csv"),
        ],
        "output": Path(
            "data/processed/health/diabetes_2006_2023.parquet"
        ),
    },
    "HYPERTENSION": {
        "indicator_name": "Hypertension",
        "files": [
            Path("data/raw/health/hypertension_2006_2019.csv"),
            Path("data/raw/health/hypertension_2020_2022.csv"),
            Path("data/raw/health/hypertension_2023.csv"),
        ],
        "output": Path(
            "data/processed/health/hypertension_2006_2023.parquet"
        ),
    },
    "HEART_FAILURE": {
        "indicator_name": "Heart failure",
        "files": [
            Path("data/raw/health/heart_failure_2006_2019.csv"),
            Path("data/raw/health/heart_failure_2020_2022.csv"),
            Path("data/raw/health/heart_failure_2023.csv"),
        ],
        "output": Path(
            "data/processed/health/heart_failure_2006_2023.parquet"
        ),
    },
    "BPCO": {
        "indicator_name": "BPCO",
        "files": [
            Path("data/raw/health/bpco_2020_2022.csv"),
            Path("data/raw/health/bpco_2023.csv"),
        ],
        "output": Path(
            "data/processed/health/bpco_2020_2023.parquet"
        ),
    },
}


HISTORICAL_HEALTH_OUTPUT = Path(
    "data/processed/health/health_indicators_historical.parquet"
)


def _read_historical_health_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Health source not found: {path}"
        )

    required_columns = {
        "ASL",
        "ANNO",
        "SESSO",
        "ETA",
        "NUMERO",
    }

    last_error: Exception | None = None

    for separator in [";", ",", "\t"]:
        try:
            frame = pd.read_csv(
                path,
                sep=separator,
                encoding="utf-8-sig",
            )

            # Normalizza eventuali spazi/BOM nei nomi colonna
            frame.columns = [
                str(column).strip()
                for column in frame.columns
            ]

            if required_columns.issubset(
                set(frame.columns)
            ):
                return frame

        except Exception as exc:
            last_error = exc

    raise ValueError(
        f"{path}: unable to detect a supported CSV format. "
        f"Expected columns: {sorted(required_columns)}"
    ) from last_error


def _normalize_historical_sex(value: object) -> str:
    normalized = str(value).strip().lower()

    mapping = {
        "f": "F",
        "femmina": "F",
        "femmine": "F",
        "female": "F",

        "m": "M",
        "maschio": "M",
        "maschi": "M",
        "male": "M",

        "all": "ALL",
        "totale": "ALL",
        "totali": "ALL",
        "tutti": "ALL",
        "entrambi": "ALL",
        "mf": "ALL",
        "m+f": "ALL",
    }

    if normalized not in mapping:
        raise ValueError(
            f"Unsupported health sex value: {value!r}"
        )

    return mapping[normalized]


def _normalize_historical_health_frame(
    frame: pd.DataFrame,
    *,
    indicator_code: str,
    indicator_name: str,
    source_file: Path,
) -> pd.DataFrame:

    # Mantiene lo stesso indice del DataFrame sorgente.
    # In questo modo le assegnazioni scalari vengono propagate
    # correttamente a tutte le righe.
    result = pd.DataFrame(index=frame.index)

    result["indicator_code"] = indicator_code
    result["indicator_name"] = indicator_name

    result["year"] = pd.to_numeric(
        frame["ANNO"],
        errors="raise",
    ).astype("int64")

    result["geographic_area"] = (
        frame["ASL"]
        .astype(str)
        .str.strip()
    )

    result["geographic_level"] = (
        result["geographic_area"]
        .eq("Puglia")
        .map({
            True: "REGION",
            False: "ASL",
        })
    )

    result["sex"] = frame["SESSO"].map(
        _normalize_historical_sex
    )

    result["age_group"] = frame["ETA"].map(
        _normalize_historical_age_group
    )

    result["cases"] = pd.to_numeric(
        frame["NUMERO"],
        errors="raise",
    ).astype("int64")

    result["source"] = (
        "Regione Puglia Open Data | "
        + source_file.name
    )

    result["quality_status"] = "VALID"

    return result.reset_index(drop=True)


def _validate_historical_health_frame(
    frame: pd.DataFrame,
    *,
    indicator_code: str,
) -> None:

    logical_key = [
        "indicator_code",
        "year",
        "geographic_area",
        "sex",
        "age_group",
    ]

    duplicates = frame.duplicated(
        subset=logical_key,
        keep=False,
    )

    if duplicates.any():
        sample = frame.loc[
            duplicates,
            logical_key,
        ].head(20)

        raise ValueError(
            f"{indicator_code}: logical duplicates detected\n"
            f"{sample.to_string(index=False)}"
        )

    if (frame["cases"] < 0).any():
        raise ValueError(
            f"{indicator_code}: negative case counts detected"
        )

    if frame["geographic_area"].isna().any():
        raise ValueError(
            f"{indicator_code}: missing geographic areas"
        )

    if frame["sex"].isna().any():
        raise ValueError(
            f"{indicator_code}: missing sex values"
        )

    if frame["age_group"].isna().any():
        raise ValueError(
            f"{indicator_code}: missing age groups"
        )


def build_historical_health_dataset(
    *,
    output_path: Path = HISTORICAL_HEALTH_OUTPUT,
) -> pd.DataFrame:
    """
    Build the historical Health dataset used by the ML research layer.

    Existing frozen 2020-2023 outputs are not modified.

    Temporal coverage:
      - DIABETES: 2006-2023
      - HYPERTENSION: 2006-2023
      - HEART_FAILURE: 2006-2023
      - BPCO: 2020-2023
    """

    indicator_frames: list[pd.DataFrame] = []

    for indicator_code, config in (
        HISTORICAL_HEALTH_SOURCES.items()
    ):
        parts: list[pd.DataFrame] = []

        for source_file in config["files"]:
            raw = _read_historical_health_csv(
                source_file
            )

            normalized = (
                _normalize_historical_health_frame(
                    raw,
                    indicator_code=indicator_code,
                    indicator_name=config[
                        "indicator_name"
                    ],
                    source_file=source_file,
                )
            )

            parts.append(normalized)

        indicator_frame = pd.concat(
            parts,
            ignore_index=True,
        )

        indicator_frame = (
            indicator_frame
            .sort_values(
                [
                    "year",
                    "geographic_area",
                    "sex",
                    "age_group",
                ]
            )
            .reset_index(drop=True)
        )

        _validate_historical_health_frame(
            indicator_frame,
            indicator_code=indicator_code,
        )

        indicator_output = config["output"]
        indicator_output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        indicator_frame.to_parquet(
            indicator_output,
            index=False,
        )

        indicator_frames.append(
            indicator_frame
        )

    historical = pd.concat(
        indicator_frames,
        ignore_index=True,
    )

    historical = (
        historical
        .sort_values(
            [
                "indicator_code",
                "year",
                "geographic_area",
                "sex",
                "age_group",
            ]
        )
        .reset_index(drop=True)
    )

    _validate_historical_health_frame(
        historical,
        indicator_code="ALL_INDICATORS",
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    historical.to_parquet(
        output_path,
        index=False,
    )

    historical_asl = (
        historical.loc[
            historical["geographic_level"] == "ASL"
        ]
        .copy()
        .reset_index(drop=True)
    )

    _validate_historical_health_frame(
        historical_asl,
        indicator_code="ALL_ASL_INDICATORS",
    )

    HISTORICAL_HEALTH_ASL_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    historical_asl.to_parquet(
        HISTORICAL_HEALTH_ASL_OUTPUT,
        index=False,
    )


    return historical

def _normalize_historical_age_group(value: object) -> str:
    normalized = str(value).strip().lower()

    mapping = {
        "40-44": "40-44",
        "45-49": "45-49",
        "50-54": "50-54",
        "55-59": "55-59",
        "60-64": "60-64",
        "65-69": "65-69",
        "70-74": "70-74",
        "75-79": "75-79",
        "80-84": "80-84",

        "85 e oltre": "85+",
        ">=85": "85+",
        "85+": "85+",
        "85 e più": "85+",
    }

    if normalized not in mapping:
        raise ValueError(
            f"Unsupported health age-group value: {value!r}"
        )

    return mapping[normalized]