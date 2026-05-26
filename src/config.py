from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[1]
DATA_DIR: Final[Path] = BASE_DIR / "data"
RAW_DIR: Final[Path] = DATA_DIR / "raw"
INTERIM_DIR: Final[Path] = DATA_DIR / "interim"
PROCESSED_DIR: Final[Path] = DATA_DIR / "processed"
DOCS_DIR: Final[Path] = BASE_DIR / "docs"
OUTPUTS_DIR: Final[Path] = BASE_DIR / "outputs"
MAPS_DIR: Final[Path] = OUTPUTS_DIR / "maps"
TABLES_DIR: Final[Path] = OUTPUTS_DIR / "tables"
QGIS_DIR: Final[Path] = OUTPUTS_DIR / "qgis"
HTML_DIR: Final[Path] = OUTPUTS_DIR / "html"
STYLES_DIR: Final[Path] = QGIS_DIR / "styles"

INTERIM_GPKG_NAME: Final[str] = "koreatown_interim.gpkg"
PROCESSED_GPKG_NAME: Final[str] = "koreatown_processed_layers.gpkg"
FINAL_GPKG_NAME: Final[str] = "koreatown_sidewalk_accessibility.gpkg"
LABELED_GEOJSON_NAME: Final[str] = "sidewalk_accessibility_labeled.geojson"
QA_ISSUES_LAYER: Final[str] = "qa_issues_points_or_polygons"
LABELED_LAYER: Final[str] = "sidewalk_accessibility_labeled"
TRANSIT_STOPS_LAYER: Final[str] = "transit_stops_clean"
AOI_LAYER: Final[str] = "aoi"
TRANSIT_BUFFER_LAYER: Final[str] = "aoi_transit_buffer"
CLEANING_STATS_NAME: Final[str] = "cleaning_stats.json"

QA_SUMMARY_CSV: Final[str] = "qa_summary.csv"
LABEL_COUNTS_CSV: Final[str] = "label_counts.csv"
SOURCE_FEATURE_COUNTS_CSV: Final[str] = "source_feature_counts.csv"
TRANSIT_STOP_COUNTS_CSV: Final[str] = "transit_stop_counts.csv"
TOP_ISSUES_CSV: Final[str] = "top_10_issue_examples.csv"
CLEANING_STATS_CSV: Final[str] = "cleaning_stats.csv"
TOP_ISSUE_EXAMPLES_LIMIT: Final[int] = 10

ARCGIS_PAGE_SIZE: Final[int] = 20_000
HTTP_TIMEOUT_SECONDS: Final[int] = 60
DOWNLOAD_TIMEOUT_SECONDS: Final[int] = 120
REQUEST_RETRIES: Final[int] = 3
USER_AGENT: Final[str] = "koreatown-sidewalk-accessibility/0.1"

NAVIGATE_LA_BASE_URL: Final[str] = (
    "https://maps.lacity.org/arcgis/rest/services/Mapping/NavigateLA/MapServer"
)
LA_TIMES_AOI_URL: Final[str] = (
    "https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/"
    "LA_Times_Neighborhoods/FeatureServer/0/query"
)
OPEN_SIDEWALKS_SCHEMA_URL: Final[str] = "https://github.com/OpenSidewalks/OpenSidewalks-Schema"

GTFS_BUS_PRIMARY_URL: Final[str] = (
    "https://gitlab.com/LACMTA/gtfs_bus/-/raw/weekly-updated-service/gtfs_bus.zip"
)
GTFS_BUS_FALLBACK_URL: Final[str] = "https://gitlab.com/LACMTA/gtfs_bus/-/raw/master/gtfs_bus.zip"
GTFS_RAIL_URL: Final[str] = "https://gitlab.com/LACMTA/gtfs_rail/-/raw/master/gtfs_rail.zip"
GTFS_BUS_ZIP_NAME: Final[str] = "gtfs_bus.zip"
GTFS_RAIL_ZIP_NAME: Final[str] = "gtfs_rail.zip"

AOI_FALLBACK_BBOX: Final[tuple[float, float, float, float]] = (
    -118.325,
    34.047,
    -118.280,
    34.085,
)
RAW_CRS: Final[str] = "EPSG:4326"
METRIC_CRS_FALLBACK: Final[str] = "EPSG:3310"
TRANSIT_BUFFER_M: Final[float] = 500.0

MISSING_RAMP_CONTEXT_M: Final[float] = 30.0
YES_RAMP_SEARCH_M: Final[float] = 25.0
SIDEWALK_CONNECTIVITY_M: Final[float] = 3.0
CROSSWALK_OR_RAMP_CONTEXT_M: Final[float] = 25.0
DRIVEWAY_BUFFER_M: Final[float] = 1.0
DRIVEWAY_OVERLAP_RATIO_THRESHOLD: Final[float] = 0.05

BASE_ACCESSIBILITY_SCORE: Final[int] = 100
MIN_ACCESSIBILITY_SCORE: Final[int] = 0
MAX_ACCESSIBILITY_SCORE: Final[int] = 100
SCORE_WEIGHTS: Final[dict[str, int]] = {
    "issue_missing_ramp": 35,
    "issue_disconnected": 25,
    "issue_driveway_conflict": 20,
    "issue_geometry_repaired": 10,
    "issue_unknown_type": 10,
}
ISSUE_COLUMNS: Final[tuple[str, ...]] = (
    "issue_missing_ramp",
    "issue_driveway_conflict",
    "issue_disconnected",
    "issue_unknown_type",
    "issue_geometry_repaired",
)
REVIEW_ISSUE_COLUMN: Final[str] = "issue_needs_review"

ALLOWED_LABELS: Final[tuple[str, ...]] = (
    "accessible",
    "missing_ramp",
    "disconnected",
    "obstacle_or_driveway_conflict",
    "needs_review",
)
LABEL_PRIORITY: Final[tuple[tuple[str, str], ...]] = (
    ("issue_needs_review", "needs_review"),
    ("issue_missing_ramp", "missing_ramp"),
    ("issue_disconnected", "disconnected"),
    ("issue_driveway_conflict", "obstacle_or_driveway_conflict"),
)
LABEL_COLORS: Final[dict[str, str]] = {
    "accessible": "#2ca25f",
    "missing_ramp": "#de2d26",
    "disconnected": "#756bb1",
    "obstacle_or_driveway_conflict": "#f16913",
    "needs_review": "#636363",
}
MAP_SOURCE_NOTE: Final[str] = (
    "Heuristic geospatial QA labels only; not an ADA compliance determination. "
    "Sources: LA City NavigateLA, LA Times, LA Metro GTFS."
)
MAP_FIGSIZE: Final[tuple[float, float]] = (11, 8.5)
MAP_DPI: Final[int] = 180

CLEAN_OUTPUT_LAYERS: Final[tuple[str, ...]] = (
    "sidewalk_polygons_clean",
    "ramps_clean",
    "driveways_clean",
    "curbs_clean",
    "parkways_clean",
    "alley_sidewalks_clean",
    "crosswalks_clean",
    "intersections_clean",
    "streets_centerline_clean",
)
FINAL_GPKG_LAYERS: Final[tuple[str, ...]] = (
    AOI_LAYER,
    LABELED_LAYER,
    *CLEAN_OUTPUT_LAYERS,
    TRANSIT_STOPS_LAYER,
    QA_ISSUES_LAYER,
)


@dataclass(frozen=True)
class ArcGISLayer:
    key: str
    layer_id: int
    name: str
    clean_layer: str
    feature_type: str

    @property
    def raw_stem(self) -> str:
        return f"navigate_la_{self.layer_id}_{self.key}"


ARCGIS_LAYERS: Final[dict[str, ArcGISLayer]] = {
    "crosswalks": ArcGISLayer("crosswalks", 157, "Crosswalks", "crosswalks_clean", "crosswalk"),
    "intersections": ArcGISLayer(
        "intersections", 300, "Intersections", "intersections_clean", "intersection"
    ),
    "access_ramps": ArcGISLayer("access_ramps", 318, "Access Ramps", "ramps_clean", "access_ramp"),
    "alley_sidewalk": ArcGISLayer(
        "alley_sidewalk", 319, "Alley Sidewalk", "alley_sidewalks_clean", "alley_sidewalk"
    ),
    "curbs": ArcGISLayer("curbs", 320, "Curbs", "curbs_clean", "curb"),
    "driveways": ArcGISLayer("driveways", 321, "Driveways", "driveways_clean", "driveway"),
    "parkways": ArcGISLayer("parkways", 322, "Parkways", "parkways_clean", "parkway"),
    "sidewalks": ArcGISLayer("sidewalks", 323, "Sidewalks", "sidewalk_polygons_clean", "sidewalk"),
    "sidewalk_area_boundary": ArcGISLayer(
        "sidewalk_area_boundary",
        325,
        "Sidewalk Area Boundary",
        "sidewalk_area_boundary_clean",
        "sidewalk",
    ),
    "streets_centerline": ArcGISLayer(
        "streets_centerline", 337, "Streets Centerline", "streets_centerline_clean", "street_centerline"
    ),
}


def ensure_directories() -> None:
    for path in (
        RAW_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        DOCS_DIR,
        MAPS_DIR,
        TABLES_DIR,
        QGIS_DIR,
        HTML_DIR,
        STYLES_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def raw_geojson_path(layer: ArcGISLayer) -> Path:
    return RAW_DIR / f"{layer.raw_stem}.geojson"


def raw_metadata_path(layer: ArcGISLayer) -> Path:
    return RAW_DIR / f"{layer.raw_stem}.metadata.json"


def processed_geojson_path(layer_name: str) -> Path:
    # Backward-compatible local export path; processed GeoPackage is preferred.
    return PROCESSED_DIR / f"{layer_name}.geojson"


def interim_geopackage_path() -> Path:
    return INTERIM_DIR / INTERIM_GPKG_NAME


def processed_geopackage_path() -> Path:
    return PROCESSED_DIR / PROCESSED_GPKG_NAME


def geopackage_path() -> Path:
    return QGIS_DIR / FINAL_GPKG_NAME


def labeled_geojson_path() -> Path:
    return QGIS_DIR / LABELED_GEOJSON_NAME
