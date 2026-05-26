# QGIS Instructions

The project does not require PyQGIS. Open the GeoPackage directly in QGIS 3.44 LTR or QGIS 4.x.

## Open The GeoPackage

1. Open QGIS.
2. Use **Layer > Add Layer > Add Vector Layer**.
3. Select `outputs/qgis/koreatown_sidewalk_accessibility.gpkg`.
4. Add the layers you want to inspect.

Recommended first layers:

- `aoi`
- `sidewalk_accessibility_labeled`
- `ramps_clean`
- `driveways_clean`
- `crosswalks_clean`
- `intersections_clean`
- `transit_stops_clean`

## Suggested Styling

Style `sidewalk_accessibility_labeled` by categorized `ai_label`:

| Label | Color |
|---|---|
| accessible | green |
| missing_ramp | red |
| disconnected | purple |
| obstacle_or_driveway_conflict | orange |
| needs_review | gray |

Style ramps as blue points, transit stops as dark blue circles, driveways as orange outlines, and the AOI as a no-fill black outline.

Optional QML starter styles are stored in `outputs/qgis/styles/`.

## Screenshot Checklist

- Full AOI map with label legend visible.
- Zoomed example of `missing_ramp`.
- Zoomed example of `obstacle_or_driveway_conflict`.
- Transit stop context view.
- Attribute table showing `ai_label`, `accessibility_score`, issue flags, and `label_reason`.

## Layout Export Checklist

- Add a title that says "heuristic QA labels" or similar.
- Add a source note for LA City NavigateLA, LA Times, and LA Metro GTFS.
- Add a scale bar and north arrow if useful.
- Avoid ADA/legal compliance language.

