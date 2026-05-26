# Data Sources

Accessed by the automated pipeline at runtime. Endpoint availability was checked during planning on May 26, 2026. The latest successful pipeline run downloaded NavigateLA layer metadata and features beginning at `2026-05-26T18:40:56+00:00`.

## LA City NavigateLA ArcGIS REST MapServer

Base endpoint:

https://maps.lacity.org/arcgis/rest/services/Mapping/NavigateLA/MapServer

Layers:

| Layer ID | Layer Name | Project Use |
|---:|---|---|
| 157 | Crosswalks | Crosswalk proximity |
| 300 | Intersections | Intersection proximity |
| 318 | Access Ramps | Ramp presence and `HASRAMP` normalization |
| 319 | Alley Sidewalk | Supporting pedestrian asset layer |
| 320 | Curbs | Supporting curb context |
| 321 | Driveways | Conflict/overlap heuristic |
| 322 | Parkways | Supporting streetscape context |
| 323 | Sidewalks | Primary labeled sidewalk polygons |
| 325 | Sidewalk Area Boundary | Supporting sidewalk boundary context |
| 337 | Streets Centerline | Map context |

Query pattern:

`https://maps.lacity.org/arcgis/rest/services/Mapping/NavigateLA/MapServer/{layer_id}/query`

The downloader sends an AOI envelope, requests GeoJSON in EPSG:4326, and uses `resultOffset` plus `resultRecordCount` pagination even when the source layer is below the service max record count.

Latest downloaded raw feature counts:

| Layer ID | Layer Name | Raw Feature Count |
|---:|---|---:|
| 157 | Crosswalks | 639 |
| 300 | Intersections | 508 |
| 318 | Access Ramps | 1,487 |
| 319 | Alley Sidewalk | 74 |
| 320 | Curbs | 20,444 |
| 321 | Driveways | 4,881 |
| 322 | Parkways | 8,521 |
| 323 | Sidewalks | 14,097 |
| 325 | Sidewalk Area Boundary | 2 |
| 337 | Streets Centerline | 1,011 |

## LA Times Neighborhood Boundaries

Koreatown AOI endpoint:

https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/LA_Times_Neighborhoods/FeatureServer/0/query?where=name%3D%27Koreatown%27&outFields=*&returnGeometry=true&outSR=4326&f=geojson

Fallback if unavailable:

`west=-118.325`, `south=34.047`, `east=-118.280`, `north=34.085`

## LA Metro GTFS

Bus primary:

https://gitlab.com/LACMTA/gtfs_bus/-/raw/weekly-updated-service/gtfs_bus.zip

Bus fallback:

https://gitlab.com/LACMTA/gtfs_bus/-/raw/master/gtfs_bus.zip

Rail:

https://gitlab.com/LACMTA/gtfs_rail/-/raw/master/gtfs_rail.zip

The pipeline reads `stops.txt`, validates latitude/longitude, converts stops to point geometries, clips to the buffered Koreatown AOI, and deduplicates by feed, stop ID, and geometry.

## OpenSidewalks Schema

Reference:

https://github.com/OpenSidewalks/OpenSidewalks-Schema

This project uses OpenSidewalks only as schema inspiration. It does not claim strict OpenSidewalks conformance.

## Terms And Licensing Note

The pipeline records source URLs and timestamps in metadata files under `data/raw/` and `data/interim/`. Before public redistribution, review current source terms from LA City, LA Times, LA Metro, and OpenSidewalks directly.
