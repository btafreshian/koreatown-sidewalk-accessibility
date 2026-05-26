from __future__ import annotations

import logging
from typing import Any

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd

from .build_aoi import estimate_metric_crs, load_aoi
from .config import (
    ALLOWED_LABELS,
    CROSSWALK_OR_RAMP_CONTEXT_M,
    DRIVEWAY_BUFFER_M,
    DRIVEWAY_OVERLAP_RATIO_THRESHOLD,
    MISSING_RAMP_CONTEXT_M,
    RAW_CRS,
    SIDEWALK_CONNECTIVITY_M,
    YES_RAMP_SEARCH_M,
)

LOGGER = logging.getLogger(__name__)


def clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _empty_distance(index: pd.Index) -> pd.Series:
    return pd.Series(np.nan, index=index, dtype="float64")


def nearest_distance_m(
    source: gpd.GeoDataFrame,
    target: gpd.GeoDataFrame,
    metric_crs: str,
) -> pd.Series:
    if source.empty or target is None or target.empty:
        return _empty_distance(source.index)
    src = source[["geometry"]].to_crs(metric_crs).copy()
    tgt = target[["geometry"]].to_crs(metric_crs).copy()
    src["_source_id"] = src.index
    try:
        joined = gpd.sjoin_nearest(src, tgt, how="left", distance_col="_distance_m")
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Nearest distance calculation failed: %s", exc)
        return _empty_distance(source.index)
    distances = joined.groupby("_source_id")["_distance_m"].min()
    return distances.reindex(source.index).astype("float64")


def _driveway_overlap(
    sidewalks_metric: gpd.GeoDataFrame,
    driveways_metric: gpd.GeoDataFrame,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    overlap_area = pd.Series(0.0, index=sidewalks_metric.index)
    overlap_ratio = pd.Series(0.0, index=sidewalks_metric.index)
    buffer_intersects = pd.Series(False, index=sidewalks_metric.index)
    if sidewalks_metric.empty or driveways_metric is None or driveways_metric.empty:
        return overlap_area, overlap_ratio, buffer_intersects

    driveway_sindex = driveways_metric.sindex
    for idx, sidewalk in sidewalks_metric.geometry.items():
        if sidewalk is None or sidewalk.is_empty:
            continue
        candidates = list(driveway_sindex.query(sidewalk.buffer(DRIVEWAY_BUFFER_M), predicate="intersects"))
        if not candidates:
            continue
        driveway_geoms = driveways_metric.iloc[candidates].geometry
        total_overlap = 0.0
        buffered = sidewalk.buffer(DRIVEWAY_BUFFER_M)
        for driveway in driveway_geoms:
            if driveway is None or driveway.is_empty:
                continue
            if buffered.intersects(driveway):
                buffer_intersects.loc[idx] = True
            if sidewalk.intersects(driveway):
                total_overlap += sidewalk.intersection(driveway).area
        overlap_area.loc[idx] = total_overlap
        area = sidewalk.area
        overlap_ratio.loc[idx] = total_overlap / area if area > 0 else 0.0
    return overlap_area, overlap_ratio, buffer_intersects


def _connectivity(sidewalks_metric: gpd.GeoDataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    touches_or_near = pd.Series(False, index=sidewalks_metric.index)
    component_id = pd.Series(-1, index=sidewalks_metric.index, dtype="int64")
    component_size = pd.Series(0, index=sidewalks_metric.index, dtype="int64")
    if sidewalks_metric.empty:
        return touches_or_near, component_id, component_size

    graph = nx.Graph()
    graph.add_nodes_from(sidewalks_metric.index)
    sindex = sidewalks_metric.sindex
    for idx, geom in sidewalks_metric.geometry.items():
        if geom is None or geom.is_empty:
            continue
        candidates = list(sindex.query(geom.buffer(SIDEWALK_CONNECTIVITY_M), predicate="intersects"))
        for pos in candidates:
            other_idx = sidewalks_metric.index[pos]
            if other_idx == idx:
                continue
            other = sidewalks_metric.iloc[pos].geometry
            if geom.touches(other) or geom.distance(other) <= SIDEWALK_CONNECTIVITY_M:
                graph.add_edge(idx, other_idx)
                touches_or_near.loc[idx] = True
                touches_or_near.loc[other_idx] = True

    for cid, nodes in enumerate(nx.connected_components(graph), start=1):
        node_list = list(nodes)
        component_id.loc[node_list] = cid
        component_size.loc[node_list] = len(node_list)
    return touches_or_near, component_id, component_size


def _label_row(row: pd.Series) -> tuple[str, str]:
    reasons = []
    if bool(row.get("issue_missing_ramp", False)):
        reasons.append("near intersection/crosswalk without nearby confirmed ramp")
    if bool(row.get("issue_disconnected", False)):
        reasons.append("isolated from nearby sidewalks and not near ramp/crosswalk")
    if bool(row.get("issue_driveway_conflict", False)):
        reasons.append("driveway overlap or 1m driveway buffer conflict")
    if bool(row.get("issue_unknown_type", False)):
        reasons.append("unknown or missing sidewalk source type")
    if bool(row.get("issue_geometry_repaired", False)):
        reasons.append("source geometry was repaired during QA")
    if bool(row.get("issue_needs_review", False)):
        label = "needs_review"
    elif bool(row.get("issue_missing_ramp", False)):
        label = "missing_ramp"
    elif bool(row.get("issue_disconnected", False)):
        label = "disconnected"
    elif bool(row.get("issue_driveway_conflict", False)):
        label = "obstacle_or_driveway_conflict"
    else:
        label = "accessible"
        reasons.append("no heuristic QA issue triggered")
    return label, "; ".join(reasons)


def build_sidewalk_labels(
    layers: dict[str, gpd.GeoDataFrame],
    transit_stops: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    sidewalks = layers.get("sidewalk_polygons_clean")
    if sidewalks is None or sidewalks.empty:
        raise RuntimeError("Cannot build labels: sidewalk_polygons_clean is empty or missing.")

    aoi = load_aoi()
    metric_crs = estimate_metric_crs(aoi)
    labeled = sidewalks.copy().reset_index(drop=True).to_crs(RAW_CRS)
    labeled["_row_id"] = labeled.index

    ramps = layers.get("ramps_clean", gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    if not ramps.empty and "has_ramp_normalized" in ramps.columns:
        yes_ramps = ramps.loc[ramps["has_ramp_normalized"].eq("yes")]
    else:
        yes_ramps = gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)
    intersections = layers.get("intersections_clean", gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    crosswalks = layers.get("crosswalks_clean", gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    driveways = layers.get("driveways_clean", gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    transit = transit_stops if transit_stops is not None else gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)

    labeled["nearest_ramp_m"] = nearest_distance_m(labeled, ramps, metric_crs)
    labeled["nearest_yes_ramp_m"] = nearest_distance_m(labeled, yes_ramps, metric_crs)
    labeled["nearest_intersection_m"] = nearest_distance_m(labeled, intersections, metric_crs)
    labeled["nearest_crosswalk_m"] = nearest_distance_m(labeled, crosswalks, metric_crs)
    labeled["nearest_transit_stop_m"] = nearest_distance_m(labeled, transit, metric_crs)

    sidewalks_metric = labeled.to_crs(metric_crs)
    driveways_metric = driveways.to_crs(metric_crs) if driveways is not None and not driveways.empty else driveways
    overlap_area, overlap_ratio, driveway_buffer_intersects = _driveway_overlap(
        sidewalks_metric,
        driveways_metric,
    )
    labeled["driveway_overlap_area_m2"] = overlap_area.values
    labeled["driveway_overlap_ratio"] = overlap_ratio.values
    labeled["driveway_buffer_intersects"] = driveway_buffer_intersects.values

    touches, component_id, component_size = _connectivity(sidewalks_metric)
    labeled["touches_or_near_other_sidewalk"] = touches.values
    labeled["component_id"] = component_id.values
    labeled["component_size"] = component_size.values

    near_intersection_or_crosswalk = (
        labeled["nearest_intersection_m"].le(MISSING_RAMP_CONTEXT_M).fillna(False)
        | labeled["nearest_crosswalk_m"].le(MISSING_RAMP_CONTEXT_M).fillna(False)
    )
    no_yes_ramp = labeled["nearest_yes_ramp_m"].isna() | labeled["nearest_yes_ramp_m"].gt(YES_RAMP_SEARCH_M)
    labeled["issue_missing_ramp"] = near_intersection_or_crosswalk & no_yes_ramp
    labeled["issue_driveway_conflict"] = (
        labeled["driveway_overlap_ratio"].gt(DRIVEWAY_OVERLAP_RATIO_THRESHOLD)
        | labeled["driveway_buffer_intersects"]
    )
    near_crosswalk_or_ramp = (
        labeled["nearest_crosswalk_m"].le(CROSSWALK_OR_RAMP_CONTEXT_M).fillna(False)
        | labeled["nearest_ramp_m"].le(CROSSWALK_OR_RAMP_CONTEXT_M).fillna(False)
    )
    labeled["issue_disconnected"] = ~labeled["touches_or_near_other_sidewalk"] & ~near_crosswalk_or_ramp
    sidewalk_type = labeled.get("sidewalk_type_normalized", pd.Series("unknown", index=labeled.index))
    labeled["issue_unknown_type"] = sidewalk_type.fillna("unknown").eq("unknown")
    labeled["issue_geometry_repaired"] = (
        labeled.get("was_invalid", pd.Series(False, index=labeled.index)).fillna(False).astype(bool)
        | labeled.get("was_repaired", pd.Series(False, index=labeled.index)).fillna(False).astype(bool)
    )

    issue_cols = [
        "issue_missing_ramp",
        "issue_driveway_conflict",
        "issue_disconnected",
        "issue_unknown_type",
        "issue_geometry_repaired",
    ]
    issue_count = labeled[issue_cols].sum(axis=1)
    missing_review_fields = labeled.get("source_object_id", pd.Series(pd.NA, index=labeled.index)).isna()
    labeled["issue_needs_review"] = issue_count.ge(2) | missing_review_fields

    score = 100
    score = score - labeled["issue_missing_ramp"].astype(int) * 35
    score = score - labeled["issue_disconnected"].astype(int) * 25
    score = score - labeled["issue_driveway_conflict"].astype(int) * 20
    score = score - labeled["issue_geometry_repaired"].astype(int) * 10
    score = score - labeled["issue_unknown_type"].astype(int) * 10
    labeled["accessibility_score"] = score.apply(clamp_score)

    label_reason = labeled.apply(_label_row, axis=1, result_type="expand")
    labeled["ai_label"] = label_reason[0]
    labeled["label_reason"] = label_reason[1]
    invalid_labels = set(labeled["ai_label"].dropna()) - set(ALLOWED_LABELS)
    if invalid_labels:
        raise ValueError(f"Unexpected labels generated: {sorted(invalid_labels)}")

    labeled = labeled.drop(columns=["_row_id"], errors="ignore").to_crs(RAW_CRS)
    qa_issues = labeled.loc[labeled[issue_cols + ["issue_needs_review"]].any(axis=1)].copy()
    return labeled, qa_issues
