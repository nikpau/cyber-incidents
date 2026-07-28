import math
from typing import Literal
from urllib.parse import quote

import dash_deck
import geopandas as gpd
import pydeck as pdk
from dash import html
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

import static
from static import APP_CACHE


def get_map_json_fast(
    base_geojson: dict,
) -> str:
    """
    Renders the map canvas component using Dash Deck and PyDeck.

    Args:
        base_geojson (dict): A dictionary containing the styled GeoJSON data.
    Returns:
        str: A JSON string representing the PyDeck map configuration.
    """
    layers = []
    base_geojson = gpd.GeoDataFrame.from_features(base_geojson["features"])
    geojson_layer = pdk.Layer(
        "GeoJsonLayer",
        data=base_geojson,
        pickable=True,
        stroked=True,
        filled=True,
        extruded=False,
        auto_highlight=True,
        highlight_color=[0, 0, 0, 60],
        get_fill_color="fill_color",
        get_line_color=[20] * 3,
        line_width_min_pixels=1,
        wrap_longitude=True,
    )
    layers.append(geojson_layer)

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=50,
            longitude=50,
            zoom=2,
            min_zoom=2,
            max_zoom=4,
            pitch=35,
            bearing=0,
        ),
        map_provider=None,
    )
    return deck.to_json()


def render_map_canvas() -> html.Div:
    """
    Renders the map canvas component using Dash Deck and PyDeck.

    Args:
        countries_geojson (gpd.GeoDataFrame): A GeoDataFrame containing the styled GeoJSON data.
        single_country_info (gpd.GeoDataFrame | None): A GeoDataFrame containing information for a single country including arcs of incidents, or None if no country is selected.

    Returns:
        html.Div: A Dash HTML Div component containing the map canvas.
    """
    return html.Div(
        className="",  # Styled via assets/layout.css
        id="map-canvas-container",
        children=[
            dash_deck.DeckGL(
                # Data is handled client-side via dcc.Store components and
                # callbacks for performance (assets/clientside_callbacks.js).
                enableEvents=["click"],
                id="map-canvas",
                style={"width": "100%", "height": "100%", "backgroundColor": "#020C18"},
                tooltip={"text": "{name}"},
            ),
        ],
    )


def country_name_for_iso(
    countries_gdf: gpd.GeoDataFrame, iso_alpha_2: str, additional_name: str
) -> str:
    selected = countries_gdf.loc[countries_gdf["iso_a2_eh"] == iso_alpha_2]
    if selected.empty:
        return "Unknown Country"

    # The "eh" iso we use to determine the country may not be unique in
    # the GeoJSON (e.g., Australia has multiple entries for its territories).
    # If we have an additional name from the GeoJSON properties, we can use
    # it to disambiguate.
    if len(selected) > 1 and additional_name:
        selected = selected.loc[selected["name"] == additional_name]

    row = selected.iloc[0]
    return (
        row.get("name")
        or row.get("admin")
        or row.get("sovereignt")
        or row.get("formal_en")
        or "Unknown Country"
    )


def geometry_for_iso(
    countries_gdf: gpd.GeoDataFrame, iso_alpha_2: str, additional_name: str
) -> BaseGeometry | None:
    selected = countries_gdf.loc[countries_gdf["iso_a2_eh"] == iso_alpha_2]
    if selected.empty:
        return None

    # The "eh" iso we use to determine the country may not be unique in
    # the GeoJSON (e.g., Australia has multiple entries for its territories).
    # If we have an additional name from the GeoJSON properties, we can use
    # it to disambiguate.
    if len(selected) > 1 and additional_name:
        selected = selected.loc[selected["name"] == additional_name]
    geometry = selected.iloc[0].get("geometry")
    if geometry is None or geometry.is_empty:
        return None
    return geometry


def build_country_shape_svg_data_uri(iso_alpha_2: str, geometry: BaseGeometry) -> str:

    empire_exceptions = [
        "FR",  # France (overseas territories)
        # "AU",  # Australia (overseas territories)
    ]

    # Extract the mainland to prevent global bounding boxes
    if iso_alpha_2 in empire_exceptions:
        geometry = (
            max(geometry.geoms, key=lambda p: p.area)
            if geometry.geom_type == "MultiPolygon"
            else geometry
        )
    minx, miny, maxx, maxy = geometry.bounds

    # If the bounding box is > 270 degrees wide,
    # it crosses the Date Line (Russia, USA, Fiji).
    if (maxx - minx) > 270:

        def fix_dateline(x, y, z=None):
            # Shift coordinates from the negative hemisphere over to the positive side
            new_x = x + 360 if x < -90 else x
            return (new_x, y) if z is None else (new_x, y, z)

        # Apply the fix to the geometry and recalculate the bounds
        geometry = transform(fix_dateline, geometry)
        minx, miny, maxx, maxy = geometry.bounds

    span_x = max(maxx - minx, 1e-9)
    span_y = max(maxy - miny, 1e-9)

    # 1. Geographic Distortion Fix (Equirectangular approximation)
    mid_lat = (miny + maxy) / 2
    cos_mid_lat = math.cos(math.radians(mid_lat))
    true_span_x = span_x * cos_mid_lat

    true_aspect_ratio = true_span_x / span_y

    # 2. Calculate dynamic UI dimensions
    MAX_CANVAS_W = 640.0
    MAX_CANVAS_H = 340.0
    padding = 8.0

    avail_w = MAX_CANVAS_W - (2 * padding)
    avail_h = avail_w / true_aspect_ratio

    if avail_h > (MAX_CANVAS_H - (2 * padding)):
        avail_h = MAX_CANVAS_H - (2 * padding)
        avail_w = avail_h * true_aspect_ratio

    canvas_w = avail_w + (2 * padding)
    canvas_h = avail_h + (2 * padding)

    # 3. Coordinate Projection Math
    # Since avail_w and avail_h are now perfectly proportional to the
    # distortion-corrected bounds, a single uniform scale factor works for both axes.
    scale = avail_h / span_y

    def project_point(x: float, y: float) -> tuple[float, float]:
        # Compress longitude (X) by the same geographic factor, then scale to pixels
        dx_true = (x - minx) * cos_mid_lat
        px = padding + (dx_true * scale)

        # Standard scale for latitude (Y), flip for SVG's top-left origin
        py = padding + avail_h - ((y - miny) * scale)
        return px, py

    path_commands: list[str] = []

    def add_ring(ring) -> None:
        coords = list(ring.coords)
        if len(coords) < 3:
            return
        first_x, first_y = project_point(coords[0][0], coords[0][1])
        commands = [f"M {first_x:.2f} {first_y:.2f}"]
        for x, y in coords[1:]:
            px, py = project_point(x, y)
            commands.append(f"L {px:.2f} {py:.2f}")
        commands.append("Z")
        path_commands.append(" ".join(commands))

    if geometry.geom_type == "Polygon":
        add_ring(geometry.exterior)
        for interior in geometry.interiors:
            add_ring(interior)
    elif geometry.geom_type == "MultiPolygon":
        for polygon in geometry.geoms:
            add_ring(polygon.exterior)
            for interior in polygon.interiors:
                add_ring(interior)

    path_data = " ".join(path_commands)

    svg = f"""
<svg xmlns='http://www.w3.org/2000/svg' width='{int(canvas_w)}' height='{int(canvas_h)}' viewBox='0 0 {int(canvas_w)} {int(canvas_h)}'>
    <path d='{path_data}' fill='#ffffff' fill-rule='evenodd'/>
</svg>
""".strip()

    return f"data:image/svg+xml;charset=utf-8,{quote(svg)}"


def get_colorbar_ticks(incident_type: Literal["attacker", "receiver"]) -> html.Div:
    """
    Returns the maximum incident count for the colorbar based on the current perspective (attacker or receiver).
    """
    max_count = APP_CACHE[incident_type]["DEFAULT"]["max_incident_count"]
    mid_count = int((max_count // 2) ** (static.COLORBAR_SCALE_FACTOR))
    return html.Div(
        className="incident-colorbar-ticks",
        children=[
            html.Span("0"),
            html.Span(str(mid_count), id="incident-colorbar-mid"),
            html.Span(str(max_count), id="incident-colorbar-max"),
        ],
    )
