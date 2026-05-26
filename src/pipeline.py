from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import geopandas as gpd

from .build_aoi import load_aoi
from .build_labels import build_sidewalk_labels
from .config import ARCGIS_LAYERS, PROCESSED_DIR, QGIS_DIR, RAW_CRS, ensure_directories, geopackage_path, processed_geojson_path
from .download_data import download_all_sources
from .make_maps import make_all_maps
from .process_gtfs import process_gtfs_stops
from .process_sidewalk_assets import process_assets
from .qa_report import write_qa_tables

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def _load_processed_layer(layer_name: str) -> gpd.GeoDataFrame:
    path = processed_geojson_path(layer_name)
    if not path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)
    return gpd.read_file(path)


def load_processed_layers() -> dict[str, gpd.GeoDataFrame]:
    layers = {layer.clean_layer: _load_processed_layer(layer.clean_layer) for layer in ARCGIS_LAYERS.values()}
    transit_path = PROCESSED_DIR / "transit_stops_clean.geojson"
    if transit_path.exists():
        layers["transit_stops_clean"] = gpd.read_file(transit_path)
    return layers


def _write_layer(gdf: gpd.GeoDataFrame, gpkg: Path, layer_name: str) -> None:
    if gdf is None or gdf.empty:
        LOGGER.warning("Skipping empty GeoPackage layer: %s", layer_name)
        return
    gdf.to_crs(RAW_CRS).to_file(gpkg, layer=layer_name, driver="GPKG")


def export_deliverables(
    aoi: gpd.GeoDataFrame,
    layers: dict[str, gpd.GeoDataFrame],
    labeled: gpd.GeoDataFrame,
    transit_stops: gpd.GeoDataFrame,
    qa_issues: gpd.GeoDataFrame,
) -> None:
    QGIS_DIR.mkdir(parents=True, exist_ok=True)
    gpkg = geopackage_path()
    if gpkg.exists():
        gpkg.unlink()

    _write_layer(aoi, gpkg, "aoi")
    _write_layer(labeled, gpkg, "sidewalk_accessibility_labeled")
    for name in (
        "sidewalk_polygons_clean",
        "ramps_clean",
        "driveways_clean",
        "curbs_clean",
        "parkways_clean",
        "alley_sidewalks_clean",
        "crosswalks_clean",
        "intersections_clean",
        "streets_centerline_clean",
    ):
        _write_layer(layers.get(name), gpkg, name)
    _write_layer(transit_stops, gpkg, "transit_stops_clean")
    _write_layer(qa_issues, gpkg, "qa_issues_points_or_polygons")

    labeled.to_crs(RAW_CRS).to_file(QGIS_DIR / "sidewalk_accessibility_labeled.geojson", driver="GeoJSON")


def _load_cleaning_stats() -> list[dict[str, Any]]:
    path = PROCESSED_DIR / "cleaning_stats.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def run_download() -> None:
    download_all_sources()


def run_process() -> tuple[gpd.GeoDataFrame, dict[str, gpd.GeoDataFrame], gpd.GeoDataFrame, gpd.GeoDataFrame]:
    aoi = load_aoi()
    layers, _stats = process_assets()
    transit_stops = process_gtfs_stops(download_missing=True)
    layers["transit_stops_clean"] = transit_stops
    labeled, qa_issues = build_sidewalk_labels(layers, transit_stops)
    labeled.to_file(PROCESSED_DIR / "sidewalk_accessibility_labeled.geojson", driver="GeoJSON")
    if not qa_issues.empty:
        qa_issues.to_file(PROCESSED_DIR / "qa_issues_points_or_polygons.geojson", driver="GeoJSON")
    export_deliverables(aoi, layers, labeled, transit_stops, qa_issues)
    return labeled, layers, transit_stops, qa_issues


def run_qa() -> None:
    layers = load_processed_layers()
    labeled_path = PROCESSED_DIR / "sidewalk_accessibility_labeled.geojson"
    labeled = gpd.read_file(labeled_path) if labeled_path.exists() else gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)
    transit = layers.get("transit_stops_clean", gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    write_qa_tables(layers, labeled, transit, _load_cleaning_stats())


def run_maps() -> None:
    aoi = load_aoi()
    layers = load_processed_layers()
    labeled = gpd.read_file(PROCESSED_DIR / "sidewalk_accessibility_labeled.geojson")
    qa_path = PROCESSED_DIR / "qa_issues_points_or_polygons.geojson"
    qa_issues = gpd.read_file(qa_path) if qa_path.exists() else labeled.iloc[0:0].copy()
    transit = layers.get("transit_stops_clean", gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    make_all_maps(aoi, layers, labeled, transit, qa_issues)


def run_pipeline() -> None:
    ensure_directories()
    run_download()
    labeled, layers, transit_stops, qa_issues = run_process()
    write_qa_tables(layers, labeled, transit_stops, _load_cleaning_stats())
    make_all_maps(load_aoi(), layers, labeled, transit_stops, qa_issues)
    LOGGER.info("Pipeline complete. GeoPackage: %s", geopackage_path())


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Build Koreatown sidewalk accessibility dataset.")
    parser.add_argument("--step", choices=["download", "process", "qa", "maps"], help="Run one pipeline step.")
    args = parser.parse_args()
    ensure_directories()
    if args.step == "download":
        run_download()
    elif args.step == "process":
        run_process()
    elif args.step == "qa":
        run_qa()
    elif args.step == "maps":
        run_maps()
    else:
        run_pipeline()


if __name__ == "__main__":
    main()
