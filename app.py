import argparse
import sys
from pathlib import Path

from dash import (
    ClientsideFunction,
    Dash,
    Input,
    Output,
    clientside_callback,
    dcc,
    html,
)

from cache import COUNTRIES_JSON, DYADIC_DATABASE_FILE, precompute_app_cache
from callbacks.map_click import register_map_click_callback
from callbacks.map_reset import register_map_reset_callback
from callbacks.map_toggle import register_perspective_toggle_callbacks
from components.inspector_card import render_inspector_card_default
from components.map import get_colorbar_ticks, get_map_json_fast, render_map_canvas
from data_helpers.db import get_colorbar_gradient_css
from data_helpers.schema import IncidentType

OXANIUM_FONT_URL = (
    "https://fonts.googleapis.com/css2?family=Oxanium:wght@200..800&display=swap"
)


def render_app_default_layout(APP_CACHE: dict) -> html.Div:
    return html.Div(
        className="fullscreen-container",  # Styled via assets/layout.css
        children=[
            dcc.Store(
                id="base-map-store",
                data=get_map_json_fast(
                    APP_CACHE[IncidentType.ATTACKER]["DEFAULT"]["base_geojson_dict"]
                ),
            ),
            dcc.Store(id="arc-data-store", data=[]),
            dcc.Store(id="selected-country-store", data=None),
            html.Div(
                className="desktop-only-content",
                children=[
                    html.Div(
                        id="map-container",
                        children=render_map_canvas(),
                    ),
                    # Headline
                    html.Div(
                        className="headline",
                        children=[
                            html.Button(
                                id="reset-map-button",
                                n_clicks=0,
                                className="floating-reset-button",
                                children=[
                                    html.Span(
                                        "Reset Map",
                                        className="reset-button-label",
                                    ),
                                ],
                            ),
                            html.H1(
                                "Global Cyber Incidents [2000 - 2025]",
                                className="headline-title",
                            ),
                            html.P(
                                "Visualizing cyber incidents between countries. "
                                "Click on a country to see the arcs of incidents.",
                                className="headline-subtitle",
                            ),
                        ],
                    ),
                    # Perspective toggle button
                    html.Div(
                        className="perspective-switch",
                        children=[
                            html.Div(
                                "Perspective", className="perspective-switch-title"
                            ),
                            html.Button(
                                id="toggle-incident-type",
                                n_clicks=0,
                                className="floating-toggle-button perspective-toggle is-attacker",
                                children=[
                                    html.Span(
                                        "Attacker",
                                        className="toggle-label toggle-label-left",
                                    ),
                                    html.Span(
                                        "Receiver",
                                        className="toggle-label toggle-label-right",
                                    ),
                                    html.Span(className="toggle-thumb"),
                                ],
                            ),
                        ],
                    ),
                    # Colorbar
                    html.Div(
                        className="incident-colorbar",
                        children=[
                            html.Div(
                                "Incident Count", className="incident-colorbar-title"
                            ),
                            html.Div(
                                "Cyber attacks carried out",
                                id="incident-colorbar-context",
                                className="incident-colorbar-context",
                            ),
                            html.Div(
                                className="incident-colorbar-track",
                                style={"background": get_colorbar_gradient_css()},
                            ),
                            get_colorbar_ticks(APP_CACHE,"attacker"),
                        ],
                    ),
                    # Affiliation notice
                    html.Div(
                        className="affiliation-notice",
                        children=[
                            html.P(
                                "© Niklas Paulig, 2026",
                            )
                        ],
                    ),
                    render_inspector_card_default(),
                    html.Div(
                        id="large-incident-modal",
                        className="incident-info-modal-shell",
                        style={"display": "none"},
                        children=[],
                    ),
                ],
            ),
            html.Div(
                className="mobile-warning-overlay",
                children=[
                    html.Div(
                        className="mobile-warning-card",
                        children=[
                            html.H2(
                                "Desktop Recommended", className="mobile-warning-title"
                            ),
                            html.P(
                                "This visualization is not optimized for mobile devices.",
                                className="mobile-warning-text",
                            ),
                            html.P(
                                "Please open this app on a desktop or laptop for the best experience.",
                                className="mobile-warning-text",
                            ),
                        ],
                    )
                ],
            ),
        ],
    )


def init_app(debug: bool = False) -> Dash | None:
    """Initializes the Dash app and returns the app instance."""

    if debug:
        if not Path("app_cache.json").exists():
            print(
                "⚠️ Warning: app_cache.json not found. "
                "Building the cache for debugging purposes. This may take a few minutes..."
            )
            APP_CACHE = precompute_app_cache(
                countries_json=COUNTRIES_JSON,
                dyadic_database_file=DYADIC_DATABASE_FILE,
                debug=True,
            )
    else:
        APP_CACHE = precompute_app_cache(
            countries_json=COUNTRIES_JSON,
            dyadic_database_file=DYADIC_DATABASE_FILE,
            debug=False,
        )

    # Init app
    app = Dash(
        name="Global Cyber Incidents",
        suppress_callback_exceptions=True,
        external_stylesheets=[OXANIUM_FONT_URL],
        title="Global Cyber Incidents",
    )

    app.layout = render_app_default_layout(APP_CACHE=APP_CACHE)

    # Callbacks
    register_perspective_toggle_callbacks(app=app, cache=APP_CACHE)
    register_map_click_callback(app=app, cache=APP_CACHE)
    register_map_reset_callback(app=app, cache=APP_CACHE)
    clientside_callback(
        ClientsideFunction(namespace="clientside", function_name="update_map_canvas"),
        Output("map-canvas", "data", allow_duplicate=True),
        Input("arc-data-store", "data"),
        Input("base-map-store", "data"),
        prevent_initial_call="initial_duplicate",
    )

    return app


if __name__ == "__main__":
    def main() -> None:
        parser = argparse.ArgumentParser(description="Run the Cyber Incidents Dash app.")
        parser.add_argument(
            "--host", type=str, default="127.0.0.1", help="Host address to run the app on."
        )
        parser.add_argument(
            "--port", type=int, default=8050, help="Port number to run the app on."
        )
        parser.add_argument(
            "--build-cache", action="store_true", help="Precompute the app cache."
        )
        parser.add_argument(
            "--debug", action="store_true", help="Run the app in debug mode."
        )
        args = parser.parse_args()

        if not Path("app_cache.json").exists() and not args.build_cache and args.debug:
            print(
                "⚠️ Warning: app_cache.json not found. "
                "Run with --build-cache to precompute the cache."
            )
            sys.exit(1)
        if args.build_cache:
            from cache import precompute_app_cache

            precompute_app_cache(
                countries_json=COUNTRIES_JSON, 
                dyadic_database_file=DYADIC_DATABASE_FILE, 
                debug=True
            )
            sys.exit(0)
        init_app().run(host=args.host, port=args.port, debug=args.debug)

else:
    # Minmal setup for running the app with gunicorn or other WSGI servers
    app = init_app()
    server = app.server
