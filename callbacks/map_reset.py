"""
Map Reset Callback Module
=========================

This module manages the reset action for the dashboard map. It restores the default
state for the inspector card and clears the current country selection, while preserving
whatever incident perspective is currently active.
"""

from dash import Input, Output, State, dash

from components.inspector_card import render_inspector_card_default
from data_helpers.schema import AppCache, IncidentType


def register_map_reset_callback(
    cache: AppCache,
    app: dash.Dash
    ) -> None:
    """
    Register the Dash callback that resets the map view.

    Args:
        cache: The application cache containing the default content for each incident
            perspective.
        app: The Dash application instance used to register the callback.
    """
    @app.callback(
        Output("inspector-card-title", "children", allow_duplicate=True),
        Output("inspector-card-image", "src", allow_duplicate=True),
        Output("inspector-card-content", "children", allow_duplicate=True),
        Output("selected-country-store", "data", allow_duplicate=True),
        Input("reset-map-button", "n_clicks"),
        State("toggle-incident-type", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_map(n_clicks, toggle_n_clicks):
        """
        Reset the map to the default global view.

        Args:
            n_clicks: The number of reset button clicks.
            toggle_n_clicks: The number of perspective toggle clicks.

        Returns:
            A tuple that clears the current arc data, restores the default inspector card,
            and removes the selected country from state.
        """
        incident_type = (
            IncidentType.ATTACKER
            if ((toggle_n_clicks or 0) % 2 == 0)
            else IncidentType.RECEIVER
        )
        default_inspector_children = render_inspector_card_default().children

        return (
            cache[incident_type]["DEFAULT"]["name"],
            cache[incident_type]["DEFAULT"]["svg"],
            default_inspector_children[2].children,
            None,
        )