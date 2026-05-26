from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .config import HTML_DIR, LABEL_COLORS, MAP_DPI, MAP_FIGSIZE, MAP_SOURCE_NOTE, MAPS_DIR, RAW_CRS

LOGGER = logging.getLogger(__name__)


def _plot_base(ax, aoi: gpd.GeoDataFrame, layers: dict[str, gpd.GeoDataFrame]) -> None:
    streets = layers.get("streets_centerline_clean")
    if streets is not None and not streets.empty:
        streets.plot(ax=ax, color="#c9c9c9", linewidth=0.35, alpha=0.7)
    aoi.boundary.plot(ax=ax, color="#111111", linewidth=1.2)


def _finalize(ax, title: str) -> None:
    ax.set_title(title, fontsize=14, pad=12)
    ax.set_axis_off()
    ax.figure.text(
        0.01,
        0.01,
        MAP_SOURCE_NOTE,
        fontsize=8,
    )
    ax.figure.tight_layout()


def _save_plot(path: Path, title: str, aoi: gpd.GeoDataFrame, layers: dict[str, gpd.GeoDataFrame], labeled: gpd.GeoDataFrame, filter_query: str | None = None) -> None:
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=MAP_FIGSIZE, dpi=MAP_DPI)
    _plot_base(ax, aoi, layers)
    data = labeled.query(filter_query).copy() if filter_query else labeled.copy()
    if not data.empty:
        for label, color in LABEL_COLORS.items():
            subset = data.loc[data["ai_label"].eq(label)]
            if not subset.empty:
                subset.plot(ax=ax, color=color, edgecolor="#333333", linewidth=0.08, alpha=0.8)
    handles = [mpatches.Patch(color=color, label=label.replace("_", " ")) for label, color in LABEL_COLORS.items()]
    ax.legend(handles=handles, loc="upper right", frameon=True, fontsize=8)
    _finalize(ax, title)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def make_static_maps(
    aoi: gpd.GeoDataFrame,
    layers: dict[str, gpd.GeoDataFrame],
    labeled: gpd.GeoDataFrame,
    transit_stops: gpd.GeoDataFrame,
    qa_issues: gpd.GeoDataFrame,
) -> None:
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    labeled_4326 = labeled.to_crs(RAW_CRS)
    aoi_4326 = aoi.to_crs(RAW_CRS)

    _save_plot(MAPS_DIR / "final_accessibility_map.png", "Koreatown Sidewalk Accessibility QA Labels", aoi_4326, layers, labeled_4326)
    _save_plot(MAPS_DIR / "missing_ramps_map.png", "Potential Missing Ramp Review Areas", aoi_4326, layers, labeled_4326, "issue_missing_ramp == True")
    _save_plot(MAPS_DIR / "driveway_conflicts_map.png", "Potential Driveway Conflict Review Areas", aoi_4326, layers, labeled_4326, "issue_driveway_conflict == True")
    _save_plot(MAPS_DIR / "qa_issues_map.png", "Sidewalk QA Issue Review Layer", aoi_4326, layers, qa_issues.to_crs(RAW_CRS) if qa_issues is not None else labeled_4326)

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=MAP_FIGSIZE, dpi=MAP_DPI)
    _plot_base(ax, aoi_4326, layers)
    labeled_4326.plot(ax=ax, color="#bdbdbd", edgecolor="none", alpha=0.35)
    if transit_stops is not None and not transit_stops.empty:
        transit_stops.to_crs(RAW_CRS).plot(ax=ax, color="#08519c", markersize=12, alpha=0.8, label="Transit stops")
        ax.legend(loc="upper right", frameon=True, fontsize=8)
    _finalize(ax, "Transit Stops Near Koreatown Sidewalk Assets")
    fig.savefig(MAPS_DIR / "transit_access_map.png", bbox_inches="tight")
    plt.close(fig)


def make_interactive_map(aoi: gpd.GeoDataFrame, labeled: gpd.GeoDataFrame, transit_stops: gpd.GeoDataFrame) -> None:
    try:
        import folium
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Skipping Folium HTML map because folium is unavailable: %s", exc)
        return

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    center = aoi.to_crs(RAW_CRS).geometry.union_all().centroid
    fmap = folium.Map(location=[center.y, center.x], zoom_start=14, tiles="CartoDB positron")
    folium.GeoJson(
        aoi.to_crs(RAW_CRS).__geo_interface__,
        name="Koreatown AOI",
        style_function=lambda _: {"fillColor": "transparent", "color": "#111111", "weight": 2},
    ).add_to(fmap)

    for label, color in LABEL_COLORS.items():
        subset = labeled.loc[labeled["ai_label"].eq(label)].to_crs(RAW_CRS)
        if subset.empty:
            continue
        folium.GeoJson(
            subset[["ai_label", "accessibility_score", "label_reason", "geometry"]].__geo_interface__,
            name=label.replace("_", " "),
            style_function=lambda _, c=color: {"fillColor": c, "color": c, "weight": 1, "fillOpacity": 0.65},
            tooltip=folium.GeoJsonTooltip(fields=["ai_label", "accessibility_score", "label_reason"]),
        ).add_to(fmap)

    if transit_stops is not None and not transit_stops.empty:
        for _, row in transit_stops.to_crs(RAW_CRS).iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=3,
                color="#08519c",
                fill=True,
                fill_opacity=0.8,
                tooltip=f"{row.get('source_feed', 'transit')}: {row.get('stop_name', row.get('stop_id', 'stop'))}",
            ).add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.get_root().html.add_child(
        folium.Element(
            "<p style='position: fixed; bottom: 10px; left: 10px; z-index: 9999; background: white; padding: 6px;'>"
            "Heuristic QA labels only; not ADA/legal findings.</p>"
        )
    )
    fmap.save(HTML_DIR / "interactive_accessibility_map.html")


def make_all_maps(
    aoi: gpd.GeoDataFrame,
    layers: dict[str, gpd.GeoDataFrame],
    labeled: gpd.GeoDataFrame,
    transit_stops: gpd.GeoDataFrame,
    qa_issues: gpd.GeoDataFrame,
) -> None:
    make_static_maps(aoi, layers, labeled, transit_stops, qa_issues)
    make_interactive_map(aoi, labeled, transit_stops)
