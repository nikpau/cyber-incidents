"""Map rendering helpers for deck.gl layers and country-shape SVG generation.

This module keeps map concerns isolated:
- Build deck.gl JSON from cached GeoJSON.
- Resolve country name/geometry from ISO code.
- Convert country geometries into compact SVG data URIs for the inspector card.
"""

import math
from urllib.parse import quote

import dash_deck
import geopandas as gpd
import pydeck as pdk
from dash import html
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

import static
from static import APP_CACHE, GeoJsonKeys, IncidentType


def get_map_json_fast(
    base_geojson: dict,
) -> str:
    """Return deck.gl JSON for the base country layer using pre-styled GeoJSON."""
    layers = []
    base_geojson = gpd.GeoDataFrame.from_features(base_geojson[GeoJsonKeys.FEATURES])
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
    """Return the Dash DeckGL container; data is injected via clientside callbacks."""
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
    """Resolve a display country name from ISO code, with optional name disambiguation."""
    selected = countries_gdf.loc[countries_gdf[GeoJsonKeys.ISO_A2_EH] == iso_alpha_2]
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
        row.get(GeoJsonKeys.NAME)
        or row.get(GeoJsonKeys.ADMIN)
        or row.get(GeoJsonKeys.SOVEREIGNT)
        or row.get(GeoJsonKeys.FORMAL_EN)
        or "Unknown Country"
    )


def geometry_for_iso(
    countries_gdf: gpd.GeoDataFrame, iso_alpha_2: str, additional_name: str
) -> BaseGeometry | None:
    """Resolve a non-empty geometry from ISO code, with optional name disambiguation."""
    selected = countries_gdf.loc[countries_gdf[GeoJsonKeys.ISO_A2_EH] == iso_alpha_2]
    if selected.empty:
        return None

    # The "eh" iso we use to determine the country may not be unique in
    # the GeoJSON (e.g., Australia has multiple entries for its territories).
    # If we have an additional name from the GeoJSON properties, we can use
    # it to disambiguate.
    if len(selected) > 1 and additional_name:
        selected = selected.loc[selected[GeoJsonKeys.NAME] == additional_name]
    geometry = selected.iloc[0].get(GeoJsonKeys.GEOMETRY)
    if geometry is None or geometry.is_empty:
        return None
    return geometry


def build_country_shape_svg_data_uri(iso_alpha_2: str, geometry: BaseGeometry) -> str:
    """Project a country geometry to a bounded SVG and return it as a data URI.

    This function solves three geographic/rendering problems:

    1. Multi-territory extraction: Countries like France include far-flung overseas
       territories in a MultiPolygon. The bounding box becomes nearly global, making
       the preview useless. For configured exceptions (FR), extract the largest polygon.

    2. Date-line wrapping: Countries spanning the international date line (Russia, USA,
       Fiji) have bounds > 270° wide. Detect this case and shift all negative longitudes
       by +360° to create a continuous range for projection.

    3. Geographic distortion correction: Mercator/equirectangular projections distort
       longitude spacing by cos(latitude). A degree at the equator is longer (in pixels)
       than a degree at 60°N. Apply cosine-latitude scaling so the country's aspect ratio
       looks correct when rendered in the inspector card.

    Output: A compact SVG data URI suitable for embedding in HTML (no network request).
    The SVG dimensions dynamically fit the country's aspect ratio within a 640×340 canvas.
    """

    empire_exceptions = [
        "FR",  # France (overseas territories)
        "AU", # Australia (remove tasmania for better visualization)
        "NL",  # Netherlands (overseas territories)
    ]

    # Multi-territory extraction: Some countries include far-flung territories
    # (e.g., France has Réunion, Guadeloupe, Martinique). The bounding box becomes
    # nearly global, rendering useless. Extract the largest polygon (mainland).
    if iso_alpha_2 in empire_exceptions:
        geometry = (
            max(geometry.geoms, key=lambda p: p.area)
            if geometry.geom_type == "MultiPolygon"
            else geometry
        )
    minx, miny, maxx, maxy = geometry.bounds

    # Date-line detection and fix: If bounding box spans > 270°, it crosses the
    # international date line (Russia spans -180°/+180°, USA spans -165° to -55°).
    # Shift all negative longitudes by +360° to unwrap the geometry.
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

    # Geographic distortion correction: Equirectangular (simple lat/lon) projection
    # compresses longitude spacing by cos(latitude). At the equator, 1° lon ≈ 111 km.
    # At 60°N, cos(60°) ≈ 0.5, so 1° lon ≈ 55 km. We apply this factor to the
    # longitude span (x-axis) before computing aspect ratio, so the rendered country
    # has the correct shape (not stretched horizontally at high latitudes).
    mid_lat = (miny + maxy) / 2
    cos_mid_lat = math.cos(math.radians(mid_lat))
    true_span_x = span_x * cos_mid_lat  # Corrected x-span in geographic units
    true_aspect_ratio = true_span_x / span_y

    # Fit to a bounded canvas (640×340) while preserving aspect ratio.
    # Algorithm: Start with max width, compute height; if too tall, swap to
    # constrain by height and recompute width. Padding adds border around the shape.
    MAX_CANVAS_W = 640.0
    MAX_CANVAS_H = 340.0
    padding = 8.0

    avail_w = MAX_CANVAS_W - (2 * padding)
    avail_h = avail_w / true_aspect_ratio

    # If height overflows, constrain by height instead
    if avail_h > (MAX_CANVAS_H - (2 * padding)):
        avail_h = MAX_CANVAS_H - (2 * padding)
        avail_w = avail_h * true_aspect_ratio

    canvas_w = avail_w + (2 * padding)
    canvas_h = avail_h + (2 * padding)

    # Single uniform scale: Since avail_w and avail_h are proportional to the
    # corrected geographic spans, one scale factor works for both axes.
    # scale = pixels per geographic unit (latitude in this case)
    scale = avail_h / span_y

    def project_point(x: float, y: float) -> tuple[float, float]:
        """Convert geographic (lon, lat) to SVG pixel coordinates.

        Apply the cosine correction to longitude, then scale both axes uniformly.
        Flip y-axis because SVG origin is top-left, but geographic coords increase upward.
        """
        # Compress longitude by cos(mid_lat), then scale from geographic to pixels
        dx_true = (x - minx) * cos_mid_lat
        px = padding + (dx_true * scale)

        # Latitude: scale uniformly, then flip (avail_h - ...) for SVG top-left origin
        dy = y - miny
        py = padding + avail_h - (dy * scale)
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


def get_colorbar_ticks(incident_type: IncidentType) -> html.Div:
    """Return colorbar ticks for the current perspective using configured scale factor."""
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
