from __future__ import annotations

import logging

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd

from .build_aoi import estimate_metric_crs, load_aoi
from .config import (
    ALLOWED_LABELS,
    BASE_ACCESSIBILITY_SCORE,
    CROSSWALK_OR_RAMP_CONTEXT_M,
    DRIVEWAY_BUFFER_M,
    DRIVEWAY_OVERLAP_RATIO_THRESHOLD,
    ISSUE_COLUMNS,
    LABEL_PRIORITY,
    MAX_ACCESSIBILITY_SCORE,
    MIN_ACCESSIBILITY_SCORE,
    MISSING_RAMP_CONTEXT_M,
    RAW_CRS,
    REVIEW_ISSUE_COLUMN,
    SCORE_WEIGHTS,
    SIDEWALK_CONNECTIVITY_M,
    YES_RAMP_SEARCH_M,
)

LOGGER = logging.getLogger(__name__)


def clamp_score(value: float) -> int:
    return int(max(MIN_ACCESSIBILITY_SCORE, min(MAX_ACCESSIBILITY_SCORE, round(value))))


def _empty_distance(index: pd.Index) -> pd.Series:
    return pd.Series(np.nan, index=index, dtype="float64")


def _metric_geometry(gdf: gpd.GeoDataFrame, metric_crs: str) -> gpd.GeoDataFrame:
    if gdf is None or gdf.empty:
        return gpd.GeoDataFrame(geometry=[], crs=metric_crs)
    return gdf[["geometry"]].to_crs(metric_crs).copy()


def nearest_distance_m(
    source_metric: gpd.GeoDataFrame,
    target_metric: gpd.GeoDataFrame,
) -> pd.Series:
    if source_metric.empty or target_metric is None or target_metric.empty:
        return _empty_distance(source_metric.index)

    source = source_metric[["geometry"]].copy()
    target = target_metric[["geometry"]].copy()
    source["_source_id"] = source.index
    try:
        joined = gpd.sjoin_nearest(source, target, how="left", distance_col="_distance_m")
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Nearest distance calculation failed: %s", exc)
        return _empty_distance(source_metric.index)
    distances = joined.groupby("_source_id")["_distance_m"].min()
    return distances.reindex(source_metric.index).astype("float64")


def _driveway_overlap(
    sidewalks_metric: gpd.GeoDataFrame,
    driveways_metric: gpd.GeoDataFrame,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    overlap_area = pd.Series(0.0, index=sidewalks_metric.index)
    overlap_ratio = pd.Series(0.0, index=sidewalks_metric.index)
    buffer_intersects = pd.Series(False, index=sidewalks_metric.index)
    if sidewalks_metric.empty or driveways_metric is None or driveways_metric.empty:
        return overlap_area, overlap_ratio, buffer_intersects

    sidewalks = sidewalks_metric[["geometry"]].copy()
    sidewalks["_sidewalk_id"] = sidewalks.index
    driveways = driveways_metric[["geometry"]].copy()
    driveways["_driveway_id"] = driveways.index

    buffered = sidewalks.copy()
    buffered["geometry"] = buffered.geometry.buffer(DRIVEWAY_BUFFER_M)
    try:
        buffer_hits = gpd.sjoin(
            buffered[["_sidewalk_id", "geometry"]],
            driveways[["_driveway_id", "geometry"]],
            how="inner",
            predicate="intersects",
        )
        if not buffer_hits.empty:
            buffer_intersects.loc[buffer_hits["_sidewalk_id"].unique()] = True
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Driveway buffer join failed: %s", exc)

    try:
        intersections = gpd.overlay(
            sidewalks[["_sidewalk_id", "geometry"]],
            driveways[["_driveway_id", "geometry"]],
            how="intersection",
            keep_geom_type=False,
        )
        if not intersections.empty:
            areas = intersections.geometry.area.groupby(intersections["_sidewalk_id"]).sum()
            overlap_area.loc[areas.index] = areas
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Driveway overlap calculation failed: %s", exc)

    sidewalk_area = sidewalks.geometry.area.replace(0, np.nan)
    overlap_ratio = (overlap_area / sidewalk_area).fillna(0.0)
    return overlap_area, overlap_ratio, buffer_intersects


def _connectivity(sidewalks_metric: gpd.GeoDataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    touches_or_near = pd.Series(False, index=sidewalks_metric.index)
    component_id = pd.Series(-1, index=sidewalks_metric.index, dtype="int64")
    component_size = pd.Series(0, index=sidewalks_metric.index, dtype="int64")
    if sidewalks_metric.empty:
        return touches_or_near, component_id, component_size

    sidewalks = sidewalks_metric[["geometry"]].copy()
    sidewalks["_sidewalk_id"] = sidewalks.index
    buffered = sidewalks.copy()
    buffered["geometry"] = buffered.geometry.buffer(SIDEWALK_CONNECTIVITY_M)
    try:
        pairs = gpd.sjoin(
            buffered[["_sidewalk_id", "geometry"]],
            sidewalks[["_sidewalk_id", "geometry"]],
            how="inner",
            predicate="intersects",
            lsuffix="left",
            rsuffix="right",
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Connectivity join failed: %s", exc)
        pairs = pd.DataFrame()

    graph = nx.Graph()
    graph.add_nodes_from(sidewalks.index)
    if not pairs.empty:
        left_col = "_sidewalk_id_left"
        right_col = "_sidewalk_id_right"
        if left_col not in pairs.columns or right_col not in pairs.columns:
            left_col = "_sidewalk_id"
            right_col = "index_right"
        for left_id, right_id in pairs[[left_col, right_col]].itertuples(index=False):
            if left_id == right_id:
                continue
            graph.add_edge(left_id, right_id)
            touches_or_near.loc[left_id] = True
            touches_or_near.loc[right_id] = True

    for cid, nodes in enumerate(nx.connected_components(graph), start=1):
        node_list = list(nodes)
        component_id.loc[node_list] = cid
        component_size.loc[node_list] = len(node_list)
    return touches_or_near, component_id, component_size


def calculate_issue_flags(labeled: pd.DataFrame) -> pd.DataFrame:
    flags = pd.DataFrame(index=labeled.index)
    near_intersection_or_crosswalk = (
        labeled["nearest_intersection_m"].le(MISSING_RAMP_CONTEXT_M).fillna(False)
        | labeled["nearest_crosswalk_m"].le(MISSING_RAMP_CONTEXT_M).fillna(False)
    )
    no_yes_ramp = labeled["nearest_yes_ramp_m"].isna() | labeled["nearest_yes_ramp_m"].gt(YES_RAMP_SEARCH_M)
    flags["issue_missing_ramp"] = near_intersection_or_crosswalk & no_yes_ramp
    flags["issue_driveway_conflict"] = (
        labeled["driveway_overlap_ratio"].gt(DRIVEWAY_OVERLAP_RATIO_THRESHOLD)
        | labeled["driveway_buffer_intersects"].fillna(False).astype(bool)
    )
    near_crosswalk_or_ramp = (
        labeled["nearest_crosswalk_m"].le(CROSSWALK_OR_RAMP_CONTEXT_M).fillna(False)
        | labeled["nearest_ramp_m"].le(CROSSWALK_OR_RAMP_CONTEXT_M).fillna(False)
    )
    flags["issue_disconnected"] = ~labeled["touches_or_near_other_sidewalk"].fillna(False).astype(bool) & ~near_crosswalk_or_ramp
    sidewalk_type = labeled.get("sidewalk_type_normalized", pd.Series("unknown", index=labeled.index))
    flags["issue_unknown_type"] = sidewalk_type.fillna("unknown").eq("unknown")
    flags["issue_geometry_repaired"] = (
        labeled.get("was_invalid", pd.Series(False, index=labeled.index)).fillna(False).astype(bool)
        | labeled.get("was_repaired", pd.Series(False, index=labeled.index)).fillna(False).astype(bool)
    )

    issue_count = flags[list(ISSUE_COLUMNS)].sum(axis=1)
    missing_review_fields = labeled.get("source_object_id", pd.Series(pd.NA, index=labeled.index)).isna()
    flags[REVIEW_ISSUE_COLUMN] = issue_count.ge(2) | missing_review_fields
    return flags.astype(bool)


def calculate_accessibility_score(flags: pd.DataFrame) -> pd.Series:
    score = pd.Series(BASE_ACCESSIBILITY_SCORE, index=flags.index, dtype="int64")
    for issue_col, penalty in SCORE_WEIGHTS.items():
        score = score - flags.get(issue_col, False).astype(int) * penalty
    return score.apply(clamp_score)


def assign_ai_label(row: pd.Series) -> str:
    for issue_col, label in LABEL_PRIORITY:
        if bool(row.get(issue_col, False)):
            return label
    return "accessible"


def build_label_reason(row: pd.Series) -> str:
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
    if not reasons:
        reasons.append("no heuristic QA issue triggered")
    return "; ".join(reasons)


def build_sidewalk_labels(
    layers: dict[str, gpd.GeoDataFrame],
    transit_stops: gpd.GeoDataFrame,
    metric_crs: str | None = None,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    sidewalks = layers.get("sidewalk_polygons_clean")
    if sidewalks is None or sidewalks.empty:
        raise RuntimeError("Cannot build labels: sidewalk_polygons_clean is empty or missing.")

    if metric_crs is None:
        metric_crs = estimate_metric_crs(load_aoi())

    labeled = sidewalks.copy().reset_index(drop=True).to_crs(RAW_CRS)
    ramps = layers.get("ramps_clean", gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    if not ramps.empty and "has_ramp_normalized" in ramps.columns:
        yes_ramps = ramps.loc[ramps["has_ramp_normalized"].eq("yes")]
    else:
        yes_ramps = gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)
    intersections = layers.get("intersections_clean", gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    crosswalks = layers.get("crosswalks_clean", gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    driveways = layers.get("driveways_clean", gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    transit = transit_stops if transit_stops is not None else gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)

    sidewalks_metric = _metric_geometry(labeled, metric_crs)
    ramps_metric = _metric_geometry(ramps, metric_crs)
    yes_ramps_metric = _metric_geometry(yes_ramps, metric_crs)
    intersections_metric = _metric_geometry(intersections, metric_crs)
    crosswalks_metric = _metric_geometry(crosswalks, metric_crs)
    driveways_metric = _metric_geometry(driveways, metric_crs)
    transit_metric = _metric_geometry(transit, metric_crs)

    labeled["nearest_ramp_m"] = nearest_distance_m(sidewalks_metric, ramps_metric).values
    labeled["nearest_yes_ramp_m"] = nearest_distance_m(sidewalks_metric, yes_ramps_metric).values
    labeled["nearest_intersection_m"] = nearest_distance_m(sidewalks_metric, intersections_metric).values
    labeled["nearest_crosswalk_m"] = nearest_distance_m(sidewalks_metric, crosswalks_metric).values
    labeled["nearest_transit_stop_m"] = nearest_distance_m(sidewalks_metric, transit_metric).values

    overlap_area, overlap_ratio, driveway_buffer_intersects = _driveway_overlap(sidewalks_metric, driveways_metric)
    labeled["driveway_overlap_area_m2"] = overlap_area.values
    labeled["driveway_overlap_ratio"] = overlap_ratio.values
    labeled["driveway_buffer_intersects"] = driveway_buffer_intersects.values

    touches, component_id, component_size = _connectivity(sidewalks_metric)
    labeled["touches_or_near_other_sidewalk"] = touches.values
    labeled["component_id"] = component_id.values
    labeled["component_size"] = component_size.values

    flags = calculate_issue_flags(labeled)
    for col in flags.columns:
        labeled[col] = flags[col].values
    labeled["accessibility_score"] = calculate_accessibility_score(flags).values
    labeled["ai_label"] = flags.apply(assign_ai_label, axis=1)
    invalid_labels = set(labeled["ai_label"].dropna()) - set(ALLOWED_LABELS)
    if invalid_labels:
        raise ValueError(f"Unexpected labels generated: {sorted(invalid_labels)}")
    labeled["label_reason"] = labeled.apply(build_label_reason, axis=1)

    issue_cols = list(ISSUE_COLUMNS) + [REVIEW_ISSUE_COLUMN]
    qa_issues = labeled.loc[labeled[issue_cols].any(axis=1)].copy()
    return labeled.to_crs(RAW_CRS), qa_issues.to_crs(RAW_CRS)
