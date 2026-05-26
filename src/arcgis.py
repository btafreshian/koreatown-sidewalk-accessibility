from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from .config import (
    ARCGIS_PAGE_SIZE,
    HTTP_TIMEOUT_SECONDS,
    NAVIGATE_LA_BASE_URL,
    RAW_CRS,
    REQUEST_RETRIES,
    USER_AGENT,
    ArcGISLayer,
)

LOGGER = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def empty_feature_collection() -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": RAW_CRS}},
        "features": [],
    }


def _request_json(
    session: requests.Session,
    url: str,
    params: dict[str, Any] | None = None,
    retries: int = REQUEST_RETRIES,
    timeout: int = HTTP_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any], int]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            status_code = response.status_code
            response.raise_for_status()
            text = response.text
            if text.lstrip().startswith("<"):
                raise ValueError("Endpoint returned HTML instead of JSON/GeoJSON")
            return response.json(), status_code
        except Exception as exc:  # noqa: BLE001 - retry and preserve exact error in metadata.
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
                continue
    raise RuntimeError(f"Failed request after {retries} attempts: {url}: {last_error}") from last_error


def fetch_layer_metadata(
    layer: ArcGISLayer,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    own_session = session is None
    session = session or requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    try:
        data, status = _request_json(session, f"{NAVIGATE_LA_BASE_URL}/{layer.layer_id}", {"f": "pjson"})
        fields = [field.get("name") for field in data.get("fields", []) if field.get("name")]
        return {
            "http_status": status,
            "service_name": data.get("name"),
            "geometry_type": data.get("geometryType"),
            "max_record_count": data.get("maxRecordCount"),
            "fields": fields,
        }
    finally:
        if own_session:
            session.close()


def query_layer_geojson(
    layer: ArcGISLayer,
    bbox: tuple[float, float, float, float],
    page_size: int = ARCGIS_PAGE_SIZE,
    retries: int = REQUEST_RETRIES,
    session: requests.Session | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    own_session = session is None
    session = session or requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    url = f"{NAVIGATE_LA_BASE_URL}/{layer.layer_id}/query"
    feature_collection = empty_feature_collection()
    metadata: dict[str, Any] = {
        "source_url": url,
        "layer_id": layer.layer_id,
        "layer_key": layer.key,
        "layer_name": layer.name,
        "fetch_timestamp_utc": utc_now_iso(),
        "http_status": None,
        "feature_count": 0,
        "crs": RAW_CRS,
        "fields": [],
        "errors": [],
        "fallback_used": False,
        "bbox": list(bbox),
    }

    offset = 0
    try:
        service_metadata = fetch_layer_metadata(layer, session=session)
        metadata.update(
            {
                "service_name": service_metadata.get("service_name"),
                "geometry_type": service_metadata.get("geometry_type"),
                "max_record_count": service_metadata.get("max_record_count"),
                "fields": service_metadata.get("fields", []),
            }
        )
    except Exception as exc:  # noqa: BLE001
        metadata["errors"].append(f"Layer metadata fetch failed: {exc}")

    try:
        while True:
            params = {
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "f": "geojson",
                "outSR": "4326",
                "geometryType": "esriGeometryEnvelope",
                "spatialRel": "esriSpatialRelIntersects",
                "inSR": "4326",
                "geometry": ",".join(str(part) for part in bbox),
                "resultOffset": offset,
                "resultRecordCount": page_size,
            }
            page, status = _request_json(session, url, params=params, retries=retries)
            metadata["http_status"] = status
            page_features = page.get("features", [])
            feature_collection["features"].extend(page_features)
            if len(page_features) < page_size:
                break
            offset += page_size
    except Exception as exc:  # noqa: BLE001
        metadata["errors"].append(str(exc))
        LOGGER.error("Failed to fetch %s: %s", layer.name, exc)
    finally:
        if own_session:
            session.close()

    metadata["feature_count"] = len(feature_collection["features"])
    if feature_collection["features"] and not metadata["fields"]:
        metadata["fields"] = sorted(feature_collection["features"][0].get("properties", {}).keys())
    return feature_collection, metadata


def save_layer_geojson(
    layer: ArcGISLayer,
    bbox: tuple[float, float, float, float],
    geojson_path: Path,
    metadata_path: Path,
) -> dict[str, Any]:
    geojson, metadata = query_layer_geojson(layer, bbox)
    if geojson.get("features"):
        geojson_path.write_text(json.dumps(geojson), encoding="utf-8")
        LOGGER.info("Saved %s features for %s", metadata["feature_count"], layer.name)
    else:
        LOGGER.warning("No features saved for %s; see metadata for details", layer.name)
        if geojson_path.exists():
            geojson_path.unlink()
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def load_metadata_files(raw_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(raw_dir.glob("*.metadata.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            records.append({"metadata_path": str(path), "errors": [f"Invalid metadata JSON: {exc}"]})
    return records
