# Labeling Logic

These labels are heuristic geospatial QA/review labels. They are not legal, engineering, or ADA compliance determinations.

## Issue Flags

`issue_missing_ramp`

True when a sidewalk feature is within 30 meters of an intersection or crosswalk, but no `HASRAMP=yes` access ramp is within 25 meters.

`issue_driveway_conflict`

True when driveway overlap ratio is greater than 0.05, or when a driveway intersects a 1 meter buffer around the sidewalk feature.

`issue_disconnected`

True when a sidewalk feature has no touching/nearby sidewalk within 3 meters and is not within 25 meters of a crosswalk or ramp.

`issue_unknown_type`

True when the source sidewalk feature type is missing or normalizes to `unknown`.

`issue_geometry_repaired`

True when the source geometry was invalid and repaired during cleaning.

`issue_needs_review`

True when multiple issue signals are present or required source identifiers are missing. This flag is intentionally conservative for portfolio QA review.

## Accessibility Score

Each sidewalk starts at 100. The score subtracts:

- 35 for `issue_missing_ramp`
- 25 for `issue_disconnected`
- 20 for `issue_driveway_conflict`
- 10 for `issue_geometry_repaired`
- 10 for `issue_unknown_type`

Scores are clamped to 0-100.

## Label Priority

When multiple conditions apply, the project assigns the highest-priority label:

1. `needs_review`
2. `missing_ramp`
3. `disconnected`
4. `obstacle_or_driveway_conflict`
5. `accessible`

All issue booleans remain in the data, and `label_reason` explains the selected label.

