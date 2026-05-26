import pytest

gpd = pytest.importorskip("geopandas")
import pandas as pd
from shapely.geometry import Polygon

from src.build_labels import (
    assign_ai_label,
    build_label_reason,
    calculate_accessibility_score,
    calculate_issue_flags,
    clamp_score,
)
from src.clean_geometries import clean_geodataframe, to_snake_case
from src.config import ALLOWED_LABELS, ISSUE_COLUMNS, REVIEW_ISSUE_COLUMN


def test_snake_case_normalization_works():
    assert to_snake_case("HASRAMP") == "hasramp"
    assert to_snake_case("Feature Type") == "feature_type"
    assert to_snake_case("Source-ID") == "source_id"


def test_score_is_clamped():
    assert clamp_score(140) == 100
    assert clamp_score(-4) == 0
    assert clamp_score(72.4) == 72


def test_labels_are_allowed():
    expected = {
        "accessible",
        "missing_ramp",
        "disconnected",
        "obstacle_or_driveway_conflict",
        "needs_review",
    }
    assert set(ALLOWED_LABELS) == expected


def test_issue_flags_score_label_and_reason_are_testable():
    frame = pd.DataFrame(
        {
            "nearest_intersection_m": [10.0],
            "nearest_crosswalk_m": [100.0],
            "nearest_yes_ramp_m": [50.0],
            "nearest_ramp_m": [50.0],
            "driveway_overlap_ratio": [0.0],
            "driveway_buffer_intersects": [False],
            "touches_or_near_other_sidewalk": [True],
            "sidewalk_type_normalized": ["sidewalk"],
            "was_invalid": [False],
            "was_repaired": [False],
            "source_object_id": ["1"],
        }
    )
    flags = calculate_issue_flags(frame)
    assert set(ISSUE_COLUMNS).issubset(flags.columns)
    assert REVIEW_ISSUE_COLUMN in flags.columns
    assert flags.loc[0, "issue_missing_ramp"]
    assert calculate_accessibility_score(flags).iloc[0] == 65
    assert assign_ai_label(flags.iloc[0]) == "missing_ramp"
    assert "confirmed ramp" in build_label_reason(flags.iloc[0])


def test_cleaning_removes_empty_and_repairs_invalid_geometry():
    invalid_bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    gdf = gpd.GeoDataFrame(
        {"ObjectID": [1, 2]},
        geometry=[invalid_bowtie, None],
        crs="EPSG:4326",
    )
    cleaned, stats = clean_geodataframe(gdf, "test", 1, metric_crs="EPSG:3310")
    assert stats["empty_geometry_count"] == 1
    assert stats["invalid_geometry_count"] == 1
    assert not cleaned.empty
    assert cleaned.geometry.notna().all()
    assert not cleaned.geometry.is_empty.any()
    assert cleaned["was_repaired"].any()

