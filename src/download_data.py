from __future__ import annotations

import logging
from pathlib import Path

import requests

from .arcgis import save_layer_geojson
from .config import (
    ARCGIS_LAYERS,
    DOWNLOAD_TIMEOUT_SECONDS,
    DOCS_DIR,
    GTFS_BUS_FALLBACK_URL,
    GTFS_BUS_PRIMARY_URL,
    GTFS_BUS_ZIP_NAME,
    GTFS_RAIL_URL,
    GTFS_RAIL_ZIP_NAME,
    RAW_DIR,
    USER_AGENT,
    ensure_directories,
    raw_geojson_path,
    raw_metadata_path,
)

LOGGER = logging.getLogger(__name__)


def write_manual_download_instructions(errors: list[str]) -> Path:
    path = DOCS_DIR / "manual_download_instructions.md"
    error_text = "\n".join(f"- {error}" for error in errors) or "- No errors recorded."
    path.write_text(
        f"""# Manual Download Instructions

The automated downloader recorded one or more source errors. Do not fabricate missing data;
download the source files below manually only if the automated retry still fails.

## Recorded Errors
{error_text}

## NavigateLA Layers
Open the NavigateLA ArcGIS REST service and query the requested layer IDs with:

- `where=1=1`
- `outFields=*`
- `returnGeometry=true`
- `f=geojson`
- `outSR=4326`
- `geometryType=esriGeometryEnvelope`
- `spatialRel=esriSpatialRelIntersects`
- `inSR=4326`
- `geometry=<koreatown bbox>`

Base service: https://maps.lacity.org/arcgis/rest/services/Mapping/NavigateLA/MapServer

## Koreatown AOI
https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/LA_Times_Neighborhoods/FeatureServer/0/query?where=name%3D%27Koreatown%27&outFields=*&returnGeometry=true&outSR=4326&f=geojson

## Metro GTFS
- Bus primary: {GTFS_BUS_PRIMARY_URL}
- Bus fallback: {GTFS_BUS_FALLBACK_URL}
- Rail: {GTFS_RAIL_URL}
""",
        encoding="utf-8",
    )
    return path


def download_file(url: str, destination: Path, retries: int = 3) -> tuple[bool, str | None]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: str | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            destination.write_bytes(response.content)
            LOGGER.info("Downloaded %s", destination)
            return True, None
        except Exception as exc:  # noqa: BLE001
            last_error = f"{url}: {exc}"
            LOGGER.warning("Download attempt %s failed for %s: %s", attempt, url, exc)
    return False, last_error


def download_gtfs_feeds() -> list[str]:
    errors: list[str] = []
    bus_path = RAW_DIR / GTFS_BUS_ZIP_NAME
    rail_path = RAW_DIR / GTFS_RAIL_ZIP_NAME

    ok, error = download_file(GTFS_BUS_PRIMARY_URL, bus_path)
    if not ok:
        errors.append(error or "Unknown bus primary GTFS failure")
        ok, error = download_file(GTFS_BUS_FALLBACK_URL, bus_path)
        if not ok:
            errors.append(error or "Unknown bus fallback GTFS failure")

    ok, error = download_file(GTFS_RAIL_URL, rail_path)
    if not ok:
        errors.append(error or "Unknown rail GTFS failure")

    return errors


def download_arcgis_layers(bbox: tuple[float, float, float, float]) -> tuple[list[dict[str, object]], list[str]]:
    errors: list[str] = []
    layer_metadata: list[dict[str, object]] = []
    for layer in ARCGIS_LAYERS.values():
        metadata = save_layer_geojson(
            layer=layer,
            bbox=bbox,
            geojson_path=raw_geojson_path(layer),
            metadata_path=raw_metadata_path(layer),
        )
        layer_metadata.append(metadata)
        errors.extend(f"{layer.name}: {error}" for error in metadata.get("errors", []))
        if metadata.get("feature_count", 0) == 0:
            errors.append(f"{layer.name}: zero features downloaded")
    return layer_metadata, errors


def download_all_sources(bbox: tuple[float, float, float, float]) -> dict[str, object]:
    ensure_directories()
    errors: list[str] = []
    layer_metadata, layer_errors = download_arcgis_layers(bbox)
    errors.extend(layer_errors)
    errors.extend(download_gtfs_feeds())
    if errors:
        write_manual_download_instructions(errors)

    return {"layers": layer_metadata, "errors": errors}
