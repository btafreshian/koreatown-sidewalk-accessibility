from pathlib import Path

import pytest

gpd = pytest.importorskip("geopandas")

from src.config import PROCESSED_DIR, QGIS_DIR, TABLES_DIR


def test_geopackage_exists_after_pipeline():
    gpkg = QGIS_DIR / "koreatown_sidewalk_accessibility.gpkg"
    if not gpkg.exists():
        pytest.skip("Run python -m src.pipeline before checking generated outputs.")
    assert gpkg.stat().st_size > 0


def test_label_counts_exists_after_pipeline():
    path = TABLES_DIR / "label_counts.csv"
    if not path.exists():
        pytest.skip("Run python -m src.pipeline before checking generated outputs.")
    assert path.stat().st_size > 0


def test_no_final_features_have_empty_geometries():
    path = PROCESSED_DIR / "sidewalk_accessibility_labeled.geojson"
    if not Path(path).exists():
        pytest.skip("Run python -m src.pipeline before checking generated outputs.")
    labeled = gpd.read_file(path)
    assert not labeled.geometry.is_empty.any()

