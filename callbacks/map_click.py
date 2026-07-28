import geopandas as gpd
from dash import Dash, Input, Output, State, no_update

from components.inspector_card import (
    render_inspector_card_content,
    render_inspector_card_default,
)
from components.map import (
    country_name_for_iso,
    geometry_for_iso,
    get_map_json_fast,
)
from static import APP_CACHE, GeoJsonKeys, DyadicCols, IncidentType


# Register the callback for handling map clicks by rendering
# the map canvas with the incident arcs for the selected country.
def register_map_click_callback(
    app: Dash,
    countries_json: dict,
) -> None:
    countries_gdf = gpd.GeoDataFrame.from_features(countries_json[GeoJsonKeys.FEATURES.value])

    @app.callback(
        Output("arc-data-store", "data"),
        Output("inspector-card-title", "children"),
        Output("inspector-card-image", "src"),
        Output("inspector-card-content", "children"),
        Input("map-canvas", "clickInfo"),
        State("toggle-incident-type", "n_clicks"),
        prevent_initial_call=True,
    )
    def handle_map_click(clickInfo, n_clicks):
        incident_type = "attacker" if ((n_clicks or 0) % 2 == 0) else "receiver"

        base_map_dict = APP_CACHE[incident_type]["DEFAULT"]["base_geojson_dict"]

        if clickInfo is None:
            # No country selected, render the default map view.
            return (
                get_map_json_fast(
                    base_geojson=base_map_dict
                ),
                APP_CACHE[incident_type]["DEFAULT"]["name"],
                APP_CACHE[incident_type]["DEFAULT"]["svg"],
                render_inspector_card_default()
                
            )

        # Extract the ISO alpha-2 country code from dash_deck picking info.
        clicked_object = (
            clickInfo.get("object") if isinstance(clickInfo, dict) 
            else None
        )
        if not clicked_object:
            return no_update, no_update, no_update, no_update

        iso_alpha_2 = (
            clicked_object.get(GeoJsonKeys.ISO_A2_EH)
            or clicked_object.get(GeoJsonKeys.PROPERTIES, {}).get(GeoJsonKeys.ISO_A2_EH)
        )
        if not iso_alpha_2:
            return no_update, no_update, no_update, no_update

        clicked_object_name = clicked_object.get("name")

        country_name = country_name_for_iso(
            countries_gdf=countries_gdf, 
            iso_alpha_2=iso_alpha_2,
            additional_name = clicked_object_name  # Fallback to GeoJSON name
        )
        geometry = geometry_for_iso(
            countries_gdf=countries_gdf, 
            iso_alpha_2=iso_alpha_2,
            additional_name=clicked_object_name  # Fallback to GeoJSON name
        )
        image_src = "/assets/eurepoc_logo.svg"
        if geometry is not None:
            image_src = APP_CACHE[incident_type][iso_alpha_2]["svg"]
            
        inspector_card_content = APP_CACHE[incident_type][iso_alpha_2]["inspector_card_content"]

        # Render the map canvas with the incident arcs for the selected country.
        return (
            APP_CACHE[incident_type][iso_alpha_2]["arc_data"],
            country_name,
            image_src,
            render_inspector_card_content(
                inspector_card_content,
            ),
        )