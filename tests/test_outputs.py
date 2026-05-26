import pytest

gpd = pytest.importorskip("geopandas")
import pandas as pd

from src.config import (
    ALLOWED_LABELS,
    DOCS_DIR,
    LABEL_COUNTS_CSV,
    LABELED_LAYER,
    QA_SUMMARY_CSV,
    SOURCE_FEATURE_COUNTS_CSV,
    TABLES_DIR,
    geopackage_path,
    processed_geopackage_path,
)


def test_geopackage_exists_after_pipeline():
    gpkg = geopackage_path()
    if not gpkg.exists():
        pytest.skip("Run python -m src.pipeline before checking generated outputs.")
    assert gpkg.stat().st_size > 0


def test_label_counts_exists_after_pipeline():
    path = TABLES_DIR / LABEL_COUNTS_CSV
    if not path.exists():
        pytest.skip("Run python -m src.pipeline before checking generated outputs.")
    assert path.stat().st_size > 0


def test_no_final_features_have_empty_geometries():
    path = processed_geopackage_path()
    if not path.exists():
        pytest.skip("Run python -m src.pipeline before checking generated outputs.")
    labeled = gpd.read_file(path, layer=LABELED_LAYER)
    assert not labeled.geometry.is_empty.any()


def test_final_scores_and_labels_are_valid_after_pipeline():
    path = processed_geopackage_path()
    if not path.exists():
        pytest.skip("Run python -m src.pipeline before checking generated outputs.")
    labeled = gpd.read_file(path, layer=LABELED_LAYER)
    assert labeled["accessibility_score"].between(0, 100).all()
    assert set(labeled["ai_label"].dropna()).issubset(set(ALLOWED_LABELS))


def test_qa_tables_have_expected_columns_after_pipeline():
    qa_summary = TABLES_DIR / QA_SUMMARY_CSV
    source_counts = TABLES_DIR / SOURCE_FEATURE_COUNTS_CSV
    if not qa_summary.exists() or not source_counts.exists():
        pytest.skip("Run python -m src.pipeline before checking generated outputs.")
    assert {"metric", "value"}.issubset(pd.read_csv(qa_summary).columns)
    assert {"source_layer", "raw_feature_count", "clean_feature_count"}.issubset(
        pd.read_csv(source_counts).columns
    )


def test_docs_pages_exist():
    assert (DOCS_DIR / "index.html").exists()
    assert (DOCS_DIR / "interactive_accessibility_map.html").exists()

