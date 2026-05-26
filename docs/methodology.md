# Methodology

## CRS Handling

Raw downloads are stored as EPSG:4326 GeoJSON. Distances, buffers, graph thresholds, and areas are never calculated in EPSG:4326.

The pipeline estimates a local UTM CRS from the Koreatown AOI with `GeoDataFrame.estimate_utm_crs()`. If that fails, it falls back to EPSG:3310. The selected metric CRS is stored in AOI and cleaning metadata.

## ArcGIS REST Pagination

NavigateLA layers are queried with:

- `where=1=1`
- `outFields=*`
- `returnGeometry=true`
- `f=geojson`
- `outSR=4326`
- AOI envelope geometry
- `resultOffset` and `resultRecordCount`

Each layer receives a raw GeoJSON file and a metadata JSON file containing source URL, layer ID, layer name, fetch timestamp, status, feature count, CRS, fields, and errors.

## Geometry Cleaning

Cleaning normalizes column names to snake_case, preserves source object IDs, removes empty geometries, repairs invalid geometries with Shapely `make_valid`, explodes multipart/collection geometries, removes exact duplicate geometries, and calculates metric `area_m2` or `length_m` when appropriate.

QA fields include:

- `was_invalid`
- `was_repaired`
- `was_empty`
- `duplicate_removed`
- `source_layer`
- `source_layer_id`
- `source_object_id`

## Spatial Joins And Distance Calculations

The labeled sidewalk layer is enriched with nearest ramp, confirmed ramp, intersection, crosswalk, and transit-stop distances. All nearest calculations are performed in the project metric CRS.

Driveway conflicts are estimated from vectorized overlap area and a 1 meter sidewalk buffer intersection.

## Graph Connectivity Approximation

The connectivity graph uses sidewalk polygons as nodes. Two sidewalk features are connected if they touch or are within 3 meters in the metric CRS. Resulting `component_id` and `component_size` values are approximate QA signals, not a routable pedestrian network.

## Export Formats

The final QGIS deliverable is:

`outputs/qgis/koreatown_sidewalk_accessibility.gpkg`

The primary labeled layer is also exported as:

`outputs/qgis/sidewalk_accessibility_labeled.geojson`

CSV QA tables are written to `outputs/tables/`, and maps are written to `outputs/maps/` plus optional Folium HTML under `outputs/html/`.

Large raw, interim, processed, and output files are generated locally and ignored by Git. The repository commits source code, tests, documentation, and the GitHub Pages demo under `docs/`.

