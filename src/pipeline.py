from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import geopandas as gpd

from .build_aoi import build_aoi_outputs, estimate_metric_crs, load_aoi
from .build_labels import build_sidewalk_labels
from .config import (
    AOI_LAYER,
    CLEAN_OUTPUT_LAYERS,
    CLEANING_STATS_NAME,
    LABELED_LAYER,
    PROCESSED_DIR,
    QGIS_DIR,
    QA_ISSUES_LAYER,
    RAW_CRS,
    TRANSIT_STOPS_LAYER,
    ensure_directories,
    geopackage_path,
    labeled_geojson_path,
    processed_geopackage_path,
)
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
    path = processed_geopackage_path()
    if not path.exists():
        return gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)
    try:
        return gpd.read_file(path, layer=layer_name)
    except Exception:  # noqa: BLE001
        return gpd.GeoDataFrame(geometry=[], crs=RAW_CRS)


def load_processed_layers() -> dict[str, gpd.GeoDataFrame]:
    layers = {layer_name: _load_processed_layer(layer_name) for layer_name in CLEAN_OUTPUT_LAYERS}
    layers[TRANSIT_STOPS_LAYER] = _load_processed_layer(TRANSIT_STOPS_LAYER)
    layers[LABELED_LAYER] = _load_processed_layer(LABELED_LAYER)
    layers[QA_ISSUES_LAYER] = _load_processed_layer(QA_ISSUES_LAYER)
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

    _write_layer(aoi, gpkg, AOI_LAYER)
    _write_layer(labeled, gpkg, LABELED_LAYER)
    for name in CLEAN_OUTPUT_LAYERS:
        _write_layer(layers.get(name), gpkg, name)
    _write_layer(transit_stops, gpkg, TRANSIT_STOPS_LAYER)
    _write_layer(qa_issues, gpkg, QA_ISSUES_LAYER)

    labeled.to_crs(RAW_CRS).to_file(labeled_geojson_path(), driver="GeoJSON")


def _load_cleaning_stats() -> list[dict[str, Any]]:
    path = PROCESSED_DIR / CLEANING_STATS_NAME
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def run_download() -> None:
    aoi, _, _ = build_aoi_outputs()
    bbox = tuple(float(value) for value in aoi.total_bounds)
    download_all_sources(bbox)


def run_process() -> tuple[gpd.GeoDataFrame, dict[str, gpd.GeoDataFrame], gpd.GeoDataFrame, gpd.GeoDataFrame]:
    aoi = load_aoi()
    metric_crs = estimate_metric_crs(aoi)
    layers, _stats = process_assets(aoi=aoi, metric_crs=metric_crs)
    transit_stops = process_gtfs_stops()
    layers[TRANSIT_STOPS_LAYER] = transit_stops
    labeled, qa_issues = build_sidewalk_labels(layers, transit_stops, metric_crs=metric_crs)
    processed_gpkg = processed_geopackage_path()
    labeled.to_file(processed_gpkg, layer=LABELED_LAYER, driver="GPKG")
    if not qa_issues.empty:
        qa_issues.to_file(processed_gpkg, layer=QA_ISSUES_LAYER, driver="GPKG")
    export_deliverables(aoi, layers, labeled, transit_stops, qa_issues)
    return labeled, layers, transit_stops, qa_issues


def run_qa() -> None:
    layers = load_processed_layers()
    labeled = layers.get(LABELED_LAYER, gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    transit = layers.get(TRANSIT_STOPS_LAYER, gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    write_qa_tables(layers, labeled, transit, _load_cleaning_stats())


def run_maps() -> None:
    aoi = load_aoi()
    layers = load_processed_layers()
    labeled = layers.get(LABELED_LAYER, gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
    if labeled.empty:
        raise RuntimeError("Cannot make maps: run process first to create the labeled layer.")
    qa_issues = layers.get(QA_ISSUES_LAYER, labeled.iloc[0:0].copy())
    transit = layers.get(TRANSIT_STOPS_LAYER, gpd.GeoDataFrame(geometry=[], crs=RAW_CRS))
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
