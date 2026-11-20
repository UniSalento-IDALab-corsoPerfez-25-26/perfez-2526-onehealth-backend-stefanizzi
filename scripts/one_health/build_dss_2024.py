"""Build the 2024 DSS supplement from observed municipal health and ASL exposures."""

from pathlib import Path

import pandas as pd
from etl.release_guard import assert_legacy_output_writable


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data/processed"
ONE_HEALTH = PROCESSED / "one_health"
MASTER = ONE_HEALTH / "one_health_master_2021_2023.parquet"
OUTPUT = ONE_HEALTH / "one_health_dss_2024.parquet"
ASLS = {"BAT", "Bari", "Brindisi", "Foggia", "Lecce", "Taranto"}
POLLUTANTS = {"NO2": "no2", "O3": "o3", "PM10": "pm10", "PM2.5": "pm2_5"}
INDICATORS = {"BPCO", "DIABETES", "HEART_FAILURE", "HYPERTENSION"}


def build_supplement() -> pd.DataFrame:
    master = pd.read_parquet(MASTER)
    health = pd.read_csv(ONE_HEALTH / "master_research_panel_v1/master_health_municipal_2020_2024.csv")
    territory = pd.read_parquet(
        PROCESSED / "demography/population_municipality_2024_2026.parquet",
        columns=["year", "municipality_code", "asl"],
    )
    territory = territory.loc[territory["year"].eq(2024), ["municipality_code", "asl"]].drop_duplicates()
    territory["municipality_code"] = pd.to_numeric(territory["municipality_code"], errors="raise")
    selected = health.loc[health["indicator"].eq("prevalence") & health["year"].isin([2023, 2024])].copy()
    selected["municipality_code"] = pd.to_numeric(selected["codice_comune"], errors="raise")
    selected["indicator_code"] = selected["pathology"].str.upper()
    selected = selected.merge(territory, on="municipality_code", how="left", validate="many_to_one")
    if (
        selected["asl"].isna().any()
        or not selected["age_scope"].eq("40_plus_as_in_source").all()
        or not selected["suppressed"].eq(False).all()
        or not selected["cases"].ge(0).all()
        or not selected["population"].gt(0).all()
        or not selected["cases"].le(selected["population"]).all()
        or selected.duplicated(["year", "indicator_code", "municipality_code"]).any()
    ):
        raise ValueError("Dati sanitari incompleti, non confrontabili o con comuni duplicati.")

    keys = ["year", "indicator_code", "asl"]
    counts = selected.groupby(["year", "indicator_code"])["municipality_code"].nunique()
    if len(counts) != 8 or not counts.eq(257).all() or set(selected["indicator_code"]) != INDICATORS:
        raise ValueError("Attesi 257 comuni per indicatore in entrambi gli anni.")
    totals = selected.groupby(keys, as_index=False)[["cases", "population"]].sum()
    archived = master.loc[master["year"].eq(2023) & master["sex"].eq("ALL")]
    archived = archived.groupby(keys)[["cases", "population"]].sum().sort_index()
    observed = totals.loc[totals["year"].eq(2023)].set_index(keys).sort_index()
    pd.testing.assert_frame_equal(observed.reset_index(), archived.reset_index(), check_dtype=False, check_exact=True)

    current = totals.loc[totals["year"].eq(2024)].copy()
    if len(current) != 24 or set(current["asl"]) != ASLS:
        raise ValueError("Attese le sei ASL per tutte le quattro patologie.")
    air = pd.read_parquet(ONE_HEALTH / "research/environmental_exposure_2010_2025_QC_v1.parquet")
    air = air.loc[air["year"].eq(2024) & air["pollutant_code"].isin(POLLUTANTS)].copy()
    if (
        len(air) != 24
        or set(air["asl"]) != ASLS
        or not air["analysis_eligible"].eq(True).all()
        or not air["mean_value"].ge(0).all()
        or not air["availability_percent"].between(0, 100).all()
    ):
        raise ValueError("Attese 24 esposizioni idonee con copertura nota.")
    air["pollutant"] = air["pollutant_code"].map(POLLUTANTS)
    wide = air.pivot(index="asl", columns="pollutant", values=["mean_value", "availability_percent"])
    if wide.isna().any().any():
        raise ValueError("Mancano combinazioni ASL-inquinante.")
    wide.columns = [f"{pollutant}_{value}" for value, pollutant in wide.columns]
    current = current.merge(wide.reset_index(), on="asl", validate="many_to_one")
    names = master.drop_duplicates("indicator_code").set_index("indicator_code")["indicator_name"]
    current["indicator_name"] = current["indicator_code"].map(names)
    current["sex"] = "ALL"
    current["age_group"] = "40+"
    current["prevalence_per_1000"] = 1000 * current["cases"] / current["population"]
    current["prevalence_percent"] = current["prevalence_per_1000"] / 10
    current["source_health"] = "Open Salute Puglia (AReSS), aggregazione comunale"
    current["source_population"] = "ISTAT, denominatori comunali del pannello sanitario"
    current["integration_quality_status"] = "VALID_WITHOUT_METEO"
    current["meteo_available"] = False
    current["meteo_is_full_year"] = False
    return current.sort_values(keys).reset_index(drop=True)


if __name__ == "__main__":
    supplement = build_supplement()
    assert_legacy_output_writable(OUTPUT)
    temporary = OUTPUT.with_suffix(".tmp")
    supplement.to_parquet(temporary, index=False)
    temporary.replace(OUTPUT)
    print(f"{len(supplement)} righe scritte in {OUTPUT.relative_to(ROOT)}")
