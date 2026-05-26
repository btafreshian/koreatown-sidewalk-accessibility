from __future__ import annotations

import logging
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd

from .config import INTERIM_DIR, PROCESSED_DIR, RAW_CRS, RAW_DIR
from .download_data import download_gtfs_feeds

LOGGER = logging.getLogger(__name__)


def _read_stops(zip_path, source_feed: str) -> gpd.GeoDataFrame:
    if not zip_path.exists():
        LOGGER.warning("GTFS zip missing for %s: %s", source_feed, zip_path)
        return gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)
    with ZipFile(zip_path) as archive:
        if "stops.txt" not in archive.namelist():
            LOGGER.warning("%s has no stops.txt", zip_path)
            return gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)
        with archive.open("stops.txt") as stops_file:
            stops = pd.read_csv(stops_file, dtype={"stop_id": "string"})

    for col in ("stop_lat", "stop_lon"):
        stops[col] = pd.to_numeric(stops[col], errors="coerce")
    stops = stops.dropna(subset=["stop_lat", "stop_lon"]).copy()
    valid = stops["stop_lat"].between(-90, 90) & stops["stop_lon"].between(-180, 180)
    stops = stops.loc[valid].copy()
    stops["source_feed"] = source_feed
    return gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
        crs=RAW_CRS,
    )


def process_gtfs_stops(download_missing: bool = True) -> gpd.GeoDataFrame:
    if download_missing and not (RAW_DIR / "gtfs_bus.zip").exists():
        download_gtfs_feeds()
    if download_missing and not (RAW_DIR / "gtfs_rail.zip").exists():
        download_gtfs_feeds()

    bus = _read_stops(RAW_DIR / "gtfs_bus.zip", "bus")
    rail = _read_stops(RAW_DIR / "gtfs_rail.zip", "rail")
    combined = pd.concat([bus, rail], ignore_index=True)
    if combined.empty:
        return gpd.GeoDataFrame(combined, geometry=[], crs=RAW_CRS)

    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs=RAW_CRS)
    buffer_path = INTERIM_DIR / "koreatown_aoi_transit_buffer.geojson"
    if buffer_path.exists():
        buffer_aoi = gpd.read_file(buffer_path).to_crs(RAW_CRS)
        combined = gpd.clip(combined, buffer_aoi)

    combined["_geometry_wkb"] = combined.geometry.apply(lambda geom: geom.wkb_hex)
    subset_cols = [col for col in ("source_feed", "stop_id", "_geometry_wkb") if col in combined.columns]
    combined = combined.drop_duplicates(subset=subset_cols).drop(columns=["_geometry_wkb"])
    combined = combined.reset_index(drop=True)

    path = PROCESSED_DIR / "transit_stops_clean.geojson"
    if not combined.empty:
        combined.to_file(path, driver="GeoJSON")
    return combined
