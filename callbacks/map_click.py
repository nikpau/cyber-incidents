"""
Map Click Callback Module
=========================

This module handles interactions with the dashboard map, including country selection,
arc selection, and modal display for incident details. It updates the inspector card,
selected-country state, and incident modal based on the active perspective.

The callback inspects Dash Deck click information and branches between:
1. A country click, which highlights that country and shows its incident arcs
2. An arc click, which opens a modal with details for the selected incident
3. A missing selection, which restores the default global view
"""

from dash import Dash, Input, Output, State, no_update

from components.info_modal import render_incident_info_modal
from components.inspector_card import (
    render_inspector_card_content,
    render_inspector_card_default,
)
from components.map import get_map_json_fast
from data_helpers.schema import AppCache, ArcInfoCols, GeoJsonKeys, IncidentType


def register_map_click_callback(
    cache: AppCache,
    app: Dash,
) -> None:
    """
    Register the Dash callback that handles map interactions.

    The callback responds to clicks on the map canvas and updates the dashboard state
    based on whether the user clicked a country, an arc, or nothing at all.

    Args:
        cache: The application cache containing country and incident data for both
            attacker and receiver perspectives.
        app: The Dash application instance used to register the callback.
    """

    @app.callback(
        Output("arc-data-store", "data"),
        Output("inspector-card-title", "children"),
        Output("inspector-card-image", "src"),
        Output("inspector-card-content", "children"),
        Output("selected-country-store", "data", allow_duplicate=True),
        Output("large-incident-modal", "children"),
        Output("large-incident-modal", "style"),
        Input("map-canvas", "clickInfo"),
        State("toggle-incident-type", "n_clicks"),
        State("selected-country-store", "data"),
        prevent_initial_call=True,
    )
    def handle_map_click(clickInfo, n_clicks, selected_country_iso):
        """
        Handle map clicks and update the relevant dashboard components.

        The callback determines the active incident perspective from the toggle button
        click count, inspects the clicked object, and then either:
        - resets to the default view when no country is selected,
        - opens a modal for a clicked arc, or
        - updates the inspector card and arc data for a clicked country.

        Args:
            clickInfo: Click data emitted by the map canvas.
            n_clicks: The number of clicks on the perspective toggle button.
            selected_country_iso: The currently selected country ISO code from shared state.

        Returns:
            A tuple containing the updated arc data, inspector card values, selected
            country state, and modal content/style.
        """
        incident_type = (
            IncidentType.ATTACKER
            if ((n_clicks or 0) % 2 == 0)
            else IncidentType.RECEIVER
        )

        base_map_dict = cache[incident_type]["DEFAULT"]["base_geojson_dict"]

        if clickInfo is None:
            # No country selected, render the default map view.
            default_inspector_children = render_inspector_card_default().children
            return (
                get_map_json_fast(base_geojson=base_map_dict),
                cache[incident_type]["DEFAULT"]["name"],
                cache[incident_type]["DEFAULT"]["svg"],
                default_inspector_children[2].children,
                None,
                [],
                {"display": "none"},
            )

        # Extract the ISO alpha-2 country code from dash_deck picking info.
        clicked_object = (
            clickInfo.get("object") if isinstance(clickInfo, dict) else None
        )
        if not clicked_object:
            return (
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                [],
                {"display": "none"},
            )

        clicked_on_arc = (
            clicked_object.get(ArcInfoCols.ORIGIN_LAT)
            and clicked_object.get(ArcInfoCols.ORIGIN_LON)
            and clicked_object.get(ArcInfoCols.DEST_LAT)
            and clicked_object.get(ArcInfoCols.DEST_LON)
        )

        # Branch I: Clicked on an arc. We open a modal with the incident details for that arc.
        if clicked_on_arc:
            selected_incident_name = clicked_object.get("name")
            modal_country_iso = selected_country_iso
            modal_country_name = cache[incident_type]["DEFAULT"]["name"]
            modal_image_src = cache[incident_type]["DEFAULT"]["svg"]
            modal_inspector_card_content = cache[incident_type]["DEFAULT"][
                "inspector_card_content"
            ]

            if modal_country_iso and modal_country_iso in cache[incident_type]:
                modal_country_name = cache[incident_type][modal_country_iso]["name"]
                modal_image_src = cache[incident_type][modal_country_iso]["svg"]
                modal_inspector_card_content = cache[incident_type][
                    modal_country_iso
                ]["inspector_card_content"]

            modal_children = render_incident_info_modal(
                inspector_card_content=modal_inspector_card_content,
                incident_arc_name=selected_incident_name,
                country_name=modal_country_name,
                image_uri=modal_image_src,
                incident_type=incident_type,
            )

            return (
                no_update,
                no_update,
                no_update,
                no_update,
                selected_country_iso,
                modal_children,
                {"display": "flex"},
            )
        else:
            # Branch II: Clicked on a country. We render the map with arcs for that country.

            iso_alpha_2 = clicked_object.get(
                GeoJsonKeys.ISO_A2_EH
            ) or clicked_object.get(GeoJsonKeys.PROPERTIES, {}).get(
                GeoJsonKeys.ISO_A2_EH
            )
            if not iso_alpha_2:
                return (
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                    [],
                    {"display": "none"},
                )

            country_name = cache[incident_type][iso_alpha_2]["name"]

            image_src = cache[incident_type][iso_alpha_2]["svg"]

            inspector_card_content = cache[incident_type][iso_alpha_2][
                "inspector_card_content"
            ]

            # Render the map canvas with the incident arcs for the selected country.
            return (
                cache[incident_type][iso_alpha_2]["arc_data"],
                country_name,
                image_src,
                render_inspector_card_content(
                    inspector_card_content,
                ),
                iso_alpha_2,
                [],
                {"display": "none"},
            )
