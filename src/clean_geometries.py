from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely import make_valid

from .config import METRIC_CRS_FALLBACK, RAW_CRS

LOGGER = logging.getLogger(__name__)


def to_snake_case(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z]+", "_", str(value).strip())
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"_+", "_", value).strip("_").lower()
    return value or "field"


def normalize_column_names(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    mapping = {col: to_snake_case(col) for col in gdf.columns if col != gdf.geometry.name}
    renamed = gdf.rename(columns=mapping).copy()
    if renamed.geometry.name != "geometry":
        renamed = renamed.rename_geometry("geometry")
    return renamed


def _first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    column_set = set(columns)
    for candidate in candidates:
        if candidate in column_set:
            return candidate
    return None


def _geometry_keys(gdf: gpd.GeoDataFrame) -> pd.Series:
    return gdf.geometry.apply(lambda geom: geom.wkb_hex if geom is not None and not geom.is_empty else None)


def _safe_metric_crs(gdf: gpd.GeoDataFrame, metric_crs: str | None) -> str:
    if metric_crs:
        return metric_crs
    try:
        estimated = gdf.estimate_utm_crs()
        if estimated:
            return estimated.to_string()
    except Exception:  # noqa: BLE001
        pass
    return METRIC_CRS_FALLBACK


def clean_geodataframe(
    gdf: gpd.GeoDataFrame,
    source_layer: str,
    source_layer_id: int | str,
    metric_crs: str | None = None,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    stats: dict[str, Any] = {
        "source_layer": source_layer,
        "source_layer_id": source_layer_id,
        "input_count": int(len(gdf)) if gdf is not None else 0,
        "empty_geometry_count": 0,
        "invalid_geometry_count": 0,
        "repaired_geometry_count": 0,
        "duplicate_geometry_count": 0,
        "output_count": 0,
    }

    if gdf is None or gdf.empty:
        empty = gpd.GeoDataFrame(
            {
                "source_layer": [],
                "source_layer_id": [],
                "source_object_id": [],
                "was_invalid": [],
                "was_repaired": [],
                "was_empty": [],
                "duplicate_removed": [],
            },
            geometry=[],
            crs=RAW_CRS,
        )
        return empty, stats

    cleaned = normalize_column_names(gdf)
    if cleaned.crs is None:
        cleaned = cleaned.set_crs(RAW_CRS)
    cleaned = cleaned.to_crs(RAW_CRS)

    source_id_col = _first_existing(
        cleaned.columns,
        ("objectid", "object_id", "fid", "id", "globalid", "global_id"),
    )
    if source_id_col:
        cleaned["source_object_id"] = cleaned[source_id_col].astype("string")
    else:
        cleaned["source_object_id"] = cleaned.index.astype(str)

    cleaned["source_layer"] = source_layer
    cleaned["source_layer_id"] = source_layer_id

    empty_mask = cleaned.geometry.isna() | cleaned.geometry.is_empty
    stats["empty_geometry_count"] = int(empty_mask.sum())
    cleaned["was_empty"] = empty_mask
    cleaned = cleaned.loc[~empty_mask].copy()
    if cleaned.empty:
        return cleaned, stats

    invalid_mask = ~cleaned.geometry.is_valid
    stats["invalid_geometry_count"] = int(invalid_mask.sum())
    cleaned["was_invalid"] = invalid_mask
    if invalid_mask.any():
        cleaned.loc[invalid_mask, "geometry"] = cleaned.loc[invalid_mask, "geometry"].apply(make_valid)
    cleaned["was_repaired"] = cleaned["was_invalid"] & cleaned.geometry.is_valid
    stats["repaired_geometry_count"] = int(cleaned["was_repaired"].sum())

    cleaned = cleaned.loc[~(cleaned.geometry.isna() | cleaned.geometry.is_empty)].copy()
    cleaned = cleaned.explode(ignore_index=True)
    cleaned = cleaned.loc[~(cleaned.geometry.isna() | cleaned.geometry.is_empty)].copy()

    geom_keys = _geometry_keys(cleaned)
    duplicate_mask = geom_keys.duplicated(keep="first")
    stats["duplicate_geometry_count"] = int(duplicate_mask.sum())
    cleaned["duplicate_removed"] = False
    cleaned = cleaned.loc[~duplicate_mask].copy()

    metric = _safe_metric_crs(cleaned, metric_crs)
    metric_gdf = cleaned.to_crs(metric)
    geom_types = metric_gdf.geometry.geom_type
    cleaned["geometry_type"] = cleaned.geometry.geom_type
    cleaned["area_m2"] = 0.0
    cleaned["length_m"] = 0.0
    polygon_mask = geom_types.isin(["Polygon", "MultiPolygon"])
    line_mask = geom_types.isin(["LineString", "MultiLineString"])
    cleaned.loc[polygon_mask, "area_m2"] = metric_gdf.loc[polygon_mask].geometry.area
    cleaned.loc[line_mask, "length_m"] = metric_gdf.loc[line_mask].geometry.length
    cleaned["metric_crs"] = metric

    stats["output_count"] = int(len(cleaned))
    return cleaned.reset_index(drop=True), stats
