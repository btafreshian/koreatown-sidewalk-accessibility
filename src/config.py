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

ALLOWED_LABELS: Final[tuple[str, ...]] = (
    "accessible",
    "missing_ramp",
    "disconnected",
    "obstacle_or_driveway_conflict",
    "needs_review",
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
    return PROCESSED_DIR / f"{layer_name}.geojson"


def geopackage_path() -> Path:
    return QGIS_DIR / "koreatown_sidewalk_accessibility.gpkg"
