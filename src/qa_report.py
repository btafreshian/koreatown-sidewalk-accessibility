from __future__ import annotations

import logging
from typing import Any

import geopandas as gpd
import pandas as pd

from .arcgis import load_metadata_files
from .config import RAW_DIR, TABLES_DIR

LOGGER = logging.getLogger(__name__)


def _clean_stats_table(cleaning_stats: list[dict[str, Any]]) -> pd.DataFrame:
    if not cleaning_stats:
        return pd.DataFrame()
    return pd.DataFrame(cleaning_stats)


def write_qa_tables(
    layers: dict[str, gpd.GeoDataFrame],
    labeled: gpd.GeoDataFrame,
    transit_stops: gpd.GeoDataFrame,
    cleaning_stats: list[dict[str, Any]],
) -> dict[str, pd.DataFrame]:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata_files(RAW_DIR)
    metadata_df = pd.DataFrame(metadata)
    stats_df = _clean_stats_table(cleaning_stats)

    source_rows = []
    for record in metadata:
        clean_layer = None
        for layer_name, gdf in layers.items():
            if str(record.get("layer_id")) == str(gdf.get("source_layer_id", pd.Series([None])).iloc[0] if not gdf.empty else ""):
                clean_layer = layer_name
                break
        source_rows.append(
            {
                "source_layer": record.get("layer_name"),
                "layer_id": record.get("layer_id"),
                "raw_feature_count": record.get("feature_count", 0),
                "clean_layer": clean_layer,
                "errors": "; ".join(record.get("errors", [])),
            }
        )
    source_feature_counts = pd.DataFrame(source_rows)
    if not stats_df.empty:
        source_feature_counts = source_feature_counts.merge(
            stats_df[["source_layer", "output_count", "invalid_geometry_count", "repaired_geometry_count", "duplicate_geometry_count", "empty_geometry_count"]],
            on="source_layer",
            how="left",
        )
        source_feature_counts = source_feature_counts.rename(columns={"output_count": "clean_feature_count"})

    label_counts = (
        labeled["ai_label"].value_counts(dropna=False).rename_axis("ai_label").reset_index(name="feature_count")
        if labeled is not None and not labeled.empty
        else pd.DataFrame(columns=["ai_label", "feature_count"])
    )
    transit_counts = (
        transit_stops["source_feed"].value_counts(dropna=False).rename_axis("source_feed").reset_index(name="stop_count")
        if transit_stops is not None and not transit_stops.empty and "source_feed" in transit_stops.columns
        else pd.DataFrame(columns=["source_feed", "stop_count"])
    )

    needs_review_pct = 0.0
    if labeled is not None and not labeled.empty:
        needs_review_pct = float((labeled["ai_label"].eq("needs_review").mean()) * 100)
    qa_summary = pd.DataFrame(
        [
            {"metric": "raw_feature_count_total", "value": int(metadata_df.get("feature_count", pd.Series(dtype=float)).fillna(0).sum()) if not metadata_df.empty else 0},
            {"metric": "clipped_clean_feature_count_total", "value": int(stats_df.get("output_count", pd.Series(dtype=float)).fillna(0).sum()) if not stats_df.empty else 0},
            {"metric": "invalid_geometry_count", "value": int(stats_df.get("invalid_geometry_count", pd.Series(dtype=float)).fillna(0).sum()) if not stats_df.empty else 0},
            {"metric": "repaired_geometry_count", "value": int(stats_df.get("repaired_geometry_count", pd.Series(dtype=float)).fillna(0).sum()) if not stats_df.empty else 0},
            {"metric": "duplicate_geometry_count", "value": int(stats_df.get("duplicate_geometry_count", pd.Series(dtype=float)).fillna(0).sum()) if not stats_df.empty else 0},
            {"metric": "empty_geometry_count", "value": int(stats_df.get("empty_geometry_count", pd.Series(dtype=float)).fillna(0).sum()) if not stats_df.empty else 0},
            {"metric": "final_sidewalk_features_count", "value": int(len(labeled)) if labeled is not None else 0},
            {"metric": "transit_stops_in_or_near_aoi", "value": int(len(transit_stops)) if transit_stops is not None else 0},
            {"metric": "needs_review_percentage", "value": round(needs_review_pct, 2)},
        ]
    )

    issue_cols = [col for col in labeled.columns if col.startswith("issue_")] if labeled is not None else []
    top_issues = (
        labeled.loc[labeled[issue_cols].any(axis=1), ["source_object_id", "ai_label", "accessibility_score", "label_reason"] + issue_cols]
        .head(10)
        .copy()
        if labeled is not None and not labeled.empty and issue_cols
        else pd.DataFrame()
    )

    source_feature_counts.to_csv(TABLES_DIR / "source_feature_counts.csv", index=False)
    label_counts.to_csv(TABLES_DIR / "label_counts.csv", index=False)
    transit_counts.to_csv(TABLES_DIR / "transit_stop_counts.csv", index=False)
    qa_summary.to_csv(TABLES_DIR / "qa_summary.csv", index=False)
    top_issues.to_csv(TABLES_DIR / "top_10_issue_examples.csv", index=False)
    stats_df.to_csv(TABLES_DIR / "cleaning_stats.csv", index=False)

    return {
        "source_feature_counts": source_feature_counts,
        "label_counts": label_counts,
        "transit_stop_counts": transit_counts,
        "qa_summary": qa_summary,
        "top_issues": top_issues,
        "cleaning_stats": stats_df,
    }
