from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from .build_aoi import estimate_metric_crs, load_aoi
from .clean_geometries import clean_geodataframe
from .config import ARCGIS_LAYERS, PROCESSED_DIR, RAW_CRS, processed_geojson_path, raw_geojson_path

LOGGER = logging.getLogger(__name__)


def _read_raw_layer(path: Path) -> gpd.GeoDataFrame:
    if not path.exists():
        LOGGER.warning("Raw layer missing: %s", path)
        return gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)
    try:
        return gpd.read_file(path)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Could not read %s: %s", path, exc)
        return gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)


def normalize_has_ramp(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    normalized = str(value).strip().lower()
    if normalized in {"yes", "y", "true", "1", "existing", "exist", "has ramp"}:
        return "yes"
    if normalized in {"no", "n", "false", "0", "none", "missing"}:
        return "no"
    if normalized in {"proposed", "prop", "planned"}:
        return "proposed"
    return "unknown"


def normalize_sidewalk_featuretype(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if "drive" in normalized:
        return "drive_sidewalk"
    if "ramp" in normalized:
        return "ramp"
    if "sidewalk" in normalized:
        return "sidewalk"
    return "unknown"


def _clip_to_aoi(gdf: gpd.GeoDataFrame, aoi: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    try:
        return gpd.clip(gdf.to_crs(RAW_CRS), aoi.to_crs(RAW_CRS))
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("AOI clip failed; keeping envelope-filtered features: %s", exc)
        return gdf


def process_assets() -> tuple[dict[str, gpd.GeoDataFrame], list[dict[str, Any]]]:
    aoi = load_aoi()
    metric_crs = estimate_metric_crs(aoi)
    layers: dict[str, gpd.GeoDataFrame] = {}
    stats: list[dict[str, Any]] = []

    for layer in ARCGIS_LAYERS.values():
        raw = _read_raw_layer(raw_geojson_path(layer))
        raw = _clip_to_aoi(raw, aoi)
        cleaned, layer_stats = clean_geodataframe(
            raw,
            source_layer=layer.name,
            source_layer_id=layer.layer_id,
            metric_crs=metric_crs,
        )
        if not cleaned.empty:
            cleaned["feature_type"] = layer.feature_type
            if layer.key == "access_ramps":
                has_ramp_col = "hasramp" if "hasramp" in cleaned.columns else None
                cleaned["has_ramp_normalized"] = (
                    cleaned[has_ramp_col].apply(normalize_has_ramp) if has_ramp_col else "unknown"
                )
            if layer.key == "sidewalks":
                feature_col = "featuretype" if "featuretype" in cleaned.columns else None
                cleaned["source_featuretype"] = cleaned[feature_col] if feature_col else pd.NA
                cleaned["sidewalk_type_normalized"] = (
                    cleaned[feature_col].apply(normalize_sidewalk_featuretype)
                    if feature_col
                    else "unknown"
                )
            if layer.key == "sidewalk_area_boundary":
                cleaned["feature_type"] = "sidewalk"

        layer_stats["clean_layer"] = layer.clean_layer
        layer_stats["metric_crs"] = metric_crs
        layers[layer.clean_layer] = cleaned
        stats.append(layer_stats)
        if not cleaned.empty:
            cleaned.to_file(processed_geojson_path(layer.clean_layer), driver="GeoJSON")

    stats_path = PROCESSED_DIR / "cleaning_stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return layers, stats
