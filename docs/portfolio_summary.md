# Portfolio Summary

I built an AI-ready sidewalk accessibility asset dataset for Koreatown, Los Angeles using public geospatial and transit data. The project downloads sidewalk, curb-ramp, driveway, crosswalk, intersection, street-centerline, and related streetscape layers from LA City NavigateLA, combines them with a Koreatown neighborhood boundary and LA Metro GTFS stops, and exports a cleaned QGIS-ready GeoPackage.

The workflow emphasizes practical geospatial data refinement: CRS-safe distance calculations, geometry validation and repair, duplicate removal, feature-type normalization, transit proximity analysis, and approximate sidewalk connectivity. Each sidewalk polygon receives transparent QA fields, an accessibility score, and a heuristic AI review label such as `accessible`, `missing_ramp`, `disconnected`, `obstacle_or_driveway_conflict`, or `needs_review`.

This project is intentionally framed as a data-quality and AI asset-preparation workflow, not an ADA compliance audit. The final deliverables include labeled GeoJSON, a multi-layer GeoPackage, QA summary tables, static maps, an optional interactive web map, and QGIS instructions for map layout review. It demonstrates how raw civic GIS layers can be transformed into documented, reproducible, model-ready geospatial assets suitable for portfolio review and downstream human-in-the-loop refinement.

