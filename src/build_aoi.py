from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import box, shape

from .config import (
    AOI_FALLBACK_BBOX,
    INTERIM_DIR,
    LA_TIMES_AOI_URL,
    METRIC_CRS_FALLBACK,
    AOI_LAYER,
    RAW_CRS,
    TRANSIT_BUFFER_M,
    TRANSIT_BUFFER_LAYER,
    ensure_directories,
    interim_geopackage_path,
    USER_AGENT,
    HTTP_TIMEOUT_SECONDS,
)

LOGGER = logging.getLogger(__name__)


def fetch_koreatown_aoi() -> tuple[gpd.GeoDataFrame, dict[str, object]]:
    params = {
        "where": "name='Koreatown'",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    }
    metadata: dict[str, object] = {
        "source_url": LA_TIMES_AOI_URL,
        "fetch_timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "fallback_used": False,
        "errors": [],
    }
    try:
        response = requests.get(
            LA_TIMES_AOI_URL,
            params=params,
            timeout=HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        )
        metadata["http_status"] = response.status_code
        response.raise_for_status()
        data = response.json()
        features = data.get("features", [])
        if not features:
            raise ValueError("LA Times query returned no Koreatown features")
        geometries = [shape(feature["geometry"]) for feature in features]
        properties = [feature.get("properties", {}) for feature in features]
        gdf = gpd.GeoDataFrame(properties, geometry=geometries, crs=RAW_CRS)
        gdf["aoi_name"] = "Koreatown"
        gdf["aoi_source"] = "LA Times Neighborhoods"
        gdf["fallback_used"] = False
        metadata["feature_count"] = len(gdf)
        return gdf, metadata
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Using fallback Koreatown bbox because AOI fetch failed: %s", exc)
        metadata["fallback_used"] = True
        metadata["errors"] = [str(exc)]
        west, south, east, north = AOI_FALLBACK_BBOX
        gdf = gpd.GeoDataFrame(
            [
                {
                    "aoi_name": "Koreatown",
                    "aoi_source": "Approximate fallback bbox",
                    "fallback_used": True,
                }
            ],
            geometry=[box(west, south, east, north)],
            crs=RAW_CRS,
        )
        metadata["feature_count"] = len(gdf)
        return gdf, metadata


def estimate_metric_crs(aoi: gpd.GeoDataFrame) -> str:
    try:
        estimated = aoi.estimate_utm_crs()
        if estimated:
            return estimated.to_string()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("AOI metric CRS estimate failed; using %s: %s", METRIC_CRS_FALLBACK, exc)
    return METRIC_CRS_FALLBACK


def buffered_aoi(aoi: gpd.GeoDataFrame, buffer_m: float = TRANSIT_BUFFER_M) -> gpd.GeoDataFrame:
    metric_crs = estimate_metric_crs(aoi)
    buffered = aoi.to_crs(metric_crs).copy()
    buffered["geometry"] = buffered.geometry.buffer(buffer_m)
    buffered["buffer_m"] = buffer_m
    buffered["metric_crs"] = metric_crs
    return buffered.to_crs(RAW_CRS)


def build_aoi_outputs() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict[str, object]]:
    ensure_directories()
    aoi, metadata = fetch_koreatown_aoi()
    metadata["metric_crs"] = estimate_metric_crs(aoi)

    aoi_path = INTERIM_DIR / "koreatown_aoi.geojson"
    buffer_path = INTERIM_DIR / "koreatown_aoi_transit_buffer.geojson"
    gpkg_path = interim_geopackage_path()
    metadata_path = INTERIM_DIR / "koreatown_aoi.metadata.json"

    aoi.to_file(aoi_path, driver="GeoJSON")
    if gpkg_path.exists():
        gpkg_path.unlink()
    aoi.to_file(gpkg_path, layer=AOI_LAYER, driver="GPKG")
    aoi_buffer = buffered_aoi(aoi)
    aoi_buffer.to_file(buffer_path, driver="GeoJSON")
    aoi_buffer.to_file(gpkg_path, layer=TRANSIT_BUFFER_LAYER, driver="GPKG")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return aoi, aoi_buffer, metadata


def load_aoi(path: Path | None = None) -> gpd.GeoDataFrame:
    path = path or (INTERIM_DIR / "koreatown_aoi.geojson")
    if not path.exists():
        gpkg = interim_geopackage_path()
        if gpkg.exists():
            return gpd.read_file(gpkg, layer=AOI_LAYER)
        aoi, _, _ = build_aoi_outputs()
        return aoi
    return gpd.read_file(path)
