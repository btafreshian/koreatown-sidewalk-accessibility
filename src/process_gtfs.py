from __future__ import annotations

import logging
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd

from .config import (
    GTFS_BUS_ZIP_NAME,
    GTFS_RAIL_ZIP_NAME,
    INTERIM_DIR,
    RAW_CRS,
    RAW_DIR,
    TRANSIT_BUFFER_LAYER,
    TRANSIT_STOPS_LAYER,
    interim_geopackage_path,
    processed_geopackage_path,
)

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


def _load_transit_buffer() -> gpd.GeoDataFrame | None:
    gpkg = interim_geopackage_path()
    if gpkg.exists():
        return gpd.read_file(gpkg, layer=TRANSIT_BUFFER_LAYER).to_crs(RAW_CRS)
    legacy_path = INTERIM_DIR / "koreatown_aoi_transit_buffer.geojson"
    if legacy_path.exists():
        return gpd.read_file(legacy_path).to_crs(RAW_CRS)
    return None


def process_gtfs_stops() -> gpd.GeoDataFrame:
    bus = _read_stops(RAW_DIR / GTFS_BUS_ZIP_NAME, "bus")
    rail = _read_stops(RAW_DIR / GTFS_RAIL_ZIP_NAME, "rail")
    combined = pd.concat([bus, rail], ignore_index=True)
    if combined.empty:
        return gpd.GeoDataFrame(combined, geometry=[], crs=RAW_CRS)

    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs=RAW_CRS)
    buffer_aoi = _load_transit_buffer()
    if buffer_aoi is not None and not buffer_aoi.empty:
        combined = gpd.clip(combined, buffer_aoi)

    combined["_geometry_wkb"] = combined.geometry.apply(lambda geom: geom.wkb_hex)
    subset_cols = [col for col in ("source_feed", "stop_id", "_geometry_wkb") if col in combined.columns]
    combined = combined.drop_duplicates(subset=subset_cols).drop(columns=["_geometry_wkb"])
    combined = combined.reset_index(drop=True)

    if not combined.empty:
        combined.to_file(processed_geopackage_path(), layer=TRANSIT_STOPS_LAYER, driver="GPKG")
    return combined
