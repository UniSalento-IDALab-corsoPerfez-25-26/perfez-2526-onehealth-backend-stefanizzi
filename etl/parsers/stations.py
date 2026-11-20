from pathlib import Path

import geopandas as gpd
import pandas as pd


def parse_stations(path: Path) -> pd.DataFrame:
    gdf = gpd.read_file(path)

    gdf.columns = [
        str(column).strip().lower().replace(" ", "_")
        for column in gdf.columns
    ]

    # Usiamo "denominazione" come nome canonico della stazione.
    # Il campo "name" presente nel GeoJSON ARPA è ridondante.
    if "name" in gdf.columns:
        gdf = gdf.drop(columns=["name"])

    mapping = {
        "id_station": "source_station_id",
        "denominazione": "name",
        "comune": "municipality",
        "provincia": "province",
        "rete": "network",
        "indirizzo": "address",
        "interesse_rete": "network_interest",
        "paese": "country_code",
        "paese_esteso": "country_name",
        "sorgente": "source_name",
        "version": "source_version",
    }

    mapping = {
        source: target
        for source, target in mapping.items()
        if source in gdf.columns
    }

    gdf = gdf.rename(columns=mapping)

    if "geometry" in gdf.columns:
        gdf["longitude"] = gdf.geometry.x
        gdf["latitude"] = gdf.geometry.y

    gdf["source"] = "ARPAP"

    # Non portiamo l'immagine Base64 nel dataset analitico.
    if "image" in gdf.columns:
        gdf = gdf.drop(columns=["image"])

    keep = [
        "source_station_id",
        "name",
        "municipality",
        "province",
        "network",
        "network_interest",
        "address",
        "country_code",
        "country_name",
        "longitude",
        "latitude",
        "source",
        "source_name",
        "source_version",
        "geometry",
    ]

    existing = [
        column
        for column in keep
        if column in gdf.columns
    ]

    return gdf[existing]