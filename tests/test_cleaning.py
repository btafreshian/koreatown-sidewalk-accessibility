import pytest

gpd = pytest.importorskip("geopandas")
from shapely.geometry import Polygon

from src.build_labels import clamp_score
from src.clean_geometries import clean_geodataframe, to_snake_case
from src.config import ALLOWED_LABELS


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

