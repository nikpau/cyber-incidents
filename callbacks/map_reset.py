from dash import Input, Output, State, dash

from components.inspector_card import render_inspector_card_default
from static import APP_CACHE, IncidentType


def register_map_reset_callback(app: dash.Dash):
    @app.callback(
        Output("arc-data-store", "data", allow_duplicate=True),
        Output("inspector-card-title", "children", allow_duplicate=True),
        Output("inspector-card-image", "src", allow_duplicate=True),
        Output("inspector-card-content", "children", allow_duplicate=True),
        Output("selected-country-store", "data", allow_duplicate=True),
        Input("reset-map-button", "n_clicks"),
        State("toggle-incident-type", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_map(n_clicks, toggle_n_clicks):
        incident_type = (
            IncidentType.ATTACKER
            if ((toggle_n_clicks or 0) % 2 == 0)
            else IncidentType.RECEIVER
        )
        default_inspector_children = render_inspector_card_default().children

        return (
            [],
            APP_CACHE[incident_type]["DEFAULT"]["name"],
            APP_CACHE[incident_type]["DEFAULT"]["svg"],
            default_inspector_children[2].children,
            None,
        )