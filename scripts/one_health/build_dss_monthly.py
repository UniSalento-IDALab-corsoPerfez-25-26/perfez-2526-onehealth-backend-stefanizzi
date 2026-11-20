"""Aggregate the September 2026 ISTAT release and the archived RRQA semester."""

import argparse
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/processed"
OUT = DATA / "one_health/operational"
PROVINCES = {"071": "Foggia", "072": "Bari", "073": "Taranto", "074": "Brindisi", "075": "Lecce", "110": "BAT"}
POLLUTANTS = ("NO2", "O3", "PM10", "PM2.5")
ISTAT_MEMBER = "comuni_giornaliero_30settembre26.csv"


def mortality(archive: Path) -> pd.DataFrame:
    columns = ["REG", "PROV", "COD_PROVCOM", "TIPO_COMUNE", "CL_ETA", "GE", "T_25", "T_26"]
    with ZipFile(archive) as source, source.open(ISTAT_MEMBER) as csv:
        puglia = pd.concat([
            chunk.loc[chunk["REG"].eq("16") & chunk["GE"].str[:2].between("01", "09")]
            for chunk in pd.read_csv(csv, usecols=columns, dtype=str, encoding="latin-1", chunksize=250_000)
        ], ignore_index=True)
    puglia["month"] = puglia["GE"].str[:2].astype(int)
    puglia["province"] = puglia["PROV"].map(PROVINCES)
    if (
        not puglia["TIPO_COMUNE"].eq("1").all()
        or puglia["COD_PROVCOM"].nunique() != 257
        or puglia["province"].isna().any()
        or puglia.duplicated(["COD_PROVCOM", "CL_ETA", "GE"]).any()
    ):
        raise ValueError("Copertura, territori o chiavi ISTAT inattesi.")
    for column in ("T_25", "T_26"):
        values = pd.to_numeric(puglia[column], errors="raise")
        if values.isna().any() or not values.ge(0).all():
            raise ValueError(f"Valori di mortalità mancanti o negativi in {column}.")
        puglia[column] = values
    grouped = puglia.groupby(["province", "month"], as_index=False)[["T_25", "T_26"]].sum()
    if len(grouped) != len(PROVINCES) * 9:
        raise ValueError("Copertura provinciale mensile incompleta.")
    return grouped.rename(columns={"T_25": "deaths_2025", "T_26": "deaths_2026"})


def air() -> pd.DataFrame:
    observations = pd.read_parquet(OUT / "rrqa_2026_h1_backfill.parquet")
    stations = pd.read_parquet(DATA / "stations.parquet", columns=["source_station_id", "network", "province"])
    observations = observations.loc[
        observations["network"].eq("RRQA") & observations["pollutant_code"].isin(POLLUTANTS)
    ].merge(stations, on=["source_station_id", "network"], how="left", validate="many_to_one")
    date = pd.to_datetime(observations["measurement_date"], errors="raise")
    observations["month"] = date.dt.month
    observations["days_in_month"] = date.dt.days_in_month
    if (
        not date.dt.year.eq(2026).all()
        or set(observations["month"]) != set(range(1, 7))
        or not observations["province"].isin(PROVINCES.values()).all()
        or not observations["unit"].eq("µg/m³").all()
        or observations.duplicated(["source_station_id", "pollutant_code", "measurement_date"]).any()
    ):
        raise ValueError("Date, territori, unità o chiavi ARPA inattesi.")
    value = pd.to_numeric(observations["value"], errors="coerce")
    observations["value"] = value.where(value.ge(0) & value.lt(float("inf")))
    keys = ["province", "month", "pollutant_code"]
    station = observations.groupby([*keys, "source_station_id"], as_index=False).agg(
        mean_value=("value", "mean"), available_days=("value", "count"), days_in_month=("days_in_month", "first"),
    )
    station["with_data"] = station["available_days"].gt(0)
    summary = station.groupby(keys, as_index=False).agg(
        mean_value=("mean_value", "mean"), stations=("with_data", "sum"),
        available_station_days=("available_days", "sum"), expected_station_days=("days_in_month", "sum"),
    )
    summary["coverage_pct"] = 100 * summary["available_station_days"] / summary["expected_station_days"]
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("istat_zip", type=Path)
    args = parser.parse_args()
    deaths = mortality(args.istat_zip)
    exposures = air()
    deaths.to_csv(OUT / "mortalita_mensile_province_2025_2026.csv", index=False)
    exposures.to_csv(OUT / "rrqa_mensile_province_2026.csv", index=False)
    print(f"ISTAT: {len(deaths)} righe. ARPA: {len(exposures)} righe.")
