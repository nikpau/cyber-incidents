"""
Map Toggle Callbacks Module
============================

This module handles the interactive map view toggling functionality for the cyber incidents
dashboard. It manages the switching between two complementary perspectives of cyber attack data:
the "attacker perspective" (viewing from the perspective of attack sources) and the
"receiver perspective" (viewing from the perspective of attack targets).

The module registers Dash callbacks that:
1. Toggle between incident perspectives when the user clicks the perspective button
2. Extract geographical location data from map click events
3. Update the map visualization, colorbar scaling, and inspector card content
4. Maintain consistent styling and UI state across view changes

Key Concepts:
- Incident Type: An enum (ATTACKER or RECEIVER) determining which perspective is active
- ISO Alpha-2 Code: Two-letter country code (e.g., 'US', 'CN') extracted from GeoJSON features
- Arc Data: Flow visualization data showing attack origins/destinations between countries
- Colorbar Scale: Logarithmic-style scaling that applies a square root transformation to
  incident counts for better visual representation of attack frequency ranges

Dependencies:
- Dash: For callback registration and reactive updates
- static.APP_CACHE: Pre-computed data structures containing GeoJSON maps, arc data,
  and inspector card content for all country/perspective combinations
- components: Rendering functions for map visualization and inspector cards
"""

from dash import Dash, Input, Output, State, no_update

import static
from components.inspector_card import (
    render_inspector_card_content,
)
from components.map import get_map_json_fast
from static import APP_CACHE


def register_map_toggle_callbacks(
    app: Dash,
) -> None:
    """
    Register Dash callbacks for toggling between attacker and receiver perspectives.

    This function registers a single Dash callback that handles the perspective toggle
    button click events. The callback manages both the view switching logic and the
    associated UI updates including map data, color scaling, and inspector card content.

    The callback uses a click counter to determine the active perspective:
    - Even click counts (0, 2, 4, ...): Attacker perspective
    - Odd click counts (1, 3, 5, ...): Receiver perspective

    This approach ensures predictable state management without requiring explicit
    state variables.

    Args:
        app (Dash): The Dash application instance to register callbacks with.
                   The app must have layout elements with the following IDs:
                   - "toggle-incident-type": The toggle button
                   - "base-map-store": Stores geojson base map data
                   - "arc-data-store": Stores flow visualization data
                   - "incident-colorbar-context": Displays perspective context label
                   - "incident-colorbar-mid": Mid-range colorbar value
                   - "incident-colorbar-max": Maximum colorbar value
                   - "inspector-card-content": Detailed country information panel
                   - "map-canvas": The deck.gl map component

    Returns:
        None

    Raises:
        KeyError: If APP_CACHE doesn't contain required data structures for the
                  active perspective and country combination.
    """

    def extract_iso_alpha_2(click_info: dict | None) -> str | None:
        """
        Extract the ISO Alpha-2 country code from a Dash deck.gl click event payload.

        When a user clicks on a country in the map visualization, Dash captures the click
        event and includes information about the clicked GeoJSON feature. This function
        safely extracts the ISO Alpha-2 country code (a two-letter code like 'US', 'CN', 'RU')
        from the nested click event structure.

        The function handles two common GeoJSON property locations:
        1. Direct property: clicked_object.iso_a2_eh
        2. Nested property: clicked_object.properties.iso_a2_eh

        This flexibility accommodates different GeoJSON feature structure conventions.

        Defensive Checks:
        - Validates that click_info is a dictionary (not None or other types)
        - Validates that the clicked_object is a dictionary
        - Gracefully returns None if any expected structure is missing

        Args:
            click_info (dict | None): The click event payload from deck.gl map component.
                                     Structure:
                                     {
                                         "object": {
                                             "iso_a2_eh": "US",  # or nested in "properties"
                                             "properties": {...}
                                         },
                                         ...other click metadata...
                                     }
                                     Can be None if no click occurred.

        Returns:
            str | None: The ISO Alpha-2 country code (e.g., 'US', 'CN', 'RU', 'FR') if
                       successfully extracted, or None if the click_info structure doesn't
                       contain expected data.

        Examples:
            >>> extract_iso_alpha_2({"object": {"iso_a2_eh": "US"}})
            'US'
            >>> extract_iso_alpha_2({"object": {"properties": {"iso_a2_eh": "CN"}}})
            'CN'
            >>> extract_iso_alpha_2(None)
            None
            >>> extract_iso_alpha_2({"object": {}})
            None
        """
        if not isinstance(click_info, dict):
            return None

        clicked_object = click_info.get("object")
        if not isinstance(clicked_object, dict):
            return None

        return clicked_object.get("iso_a2_eh") or clicked_object.get(
            "properties", {}
        ).get("iso_a2_eh")

    @app.callback(
        Output("base-map-store", "data", allow_duplicate=True),
        Output("arc-data-store", "data", allow_duplicate=True),
        Output("toggle-incident-type", "className"),
        Output("incident-colorbar-context", "children"),
        Output("incident-colorbar-mid", "children"),
        Output("incident-colorbar-max", "children"),
        Output("inspector-card-content", "children", allow_duplicate=True),
        Input("toggle-incident-type", "n_clicks"),
        State("map-canvas", "clickInfo"),
        prevent_initial_call=True,
    )
    def toggle_incident_type(n_clicks: int, clickInfo):
        """
        Toggle between attacker and receiver perspectives and update all related visualizations.

        This is the main callback that orchestrates the entire perspective switching experience.
        It's triggered whenever the user clicks the perspective toggle button, and it handles:

        1. **Perspective Determination**: Uses click count parity to determine which perspective
           is active (even = attacker, odd = receiver)

        2. **Incident Type Selection**: Maps the perspective to the corresponding incident
           type enum value from the static configuration

        3. **Colorbar Scaling**: Computes colorbar midpoint and maximum values using a square-root
           transformation. This logarithmic-style scaling makes the color gradient more
           intuitive when incident counts span multiple orders of magnitude.
           - Raw max_count: actual maximum incidents from data
           - Square-root transformation: sqrt(max_count // 2) for midpoint, sqrt(max_count)
             for max
           - Rationale: Makes visual color differences more linear in perceived incident counts

        4. **UI State Management**: Updates button styling to reflect the active perspective
           with CSS classes that trigger animations and visual changes

        5. **Context Labels**: Provides human-readable labels for the colorbar explaining
           which perspective is currently active

        6. **Data Rendering**: Retrieves pre-computed visualization data from APP_CACHE and
           renders appropriate map geojson and flow arcs

        7. **Country-Specific Updates**: If a country is selected (clickInfo is not None),
           updates the inspector card to show detailed information about that country's
           incident statistics for the active perspective

        Callback Outputs Explained:
        - base-map-store: GeoJSON data for the base map (same for all perspectives)
        - arc-data-store: Flow visualization data (arrows between countries showing attacks)
        - toggle-incident-type: CSS class name controlling button styling and animations
        - incident-colorbar-context: Text label ("Attacker perspective" or "Receiver perspective")
        - incident-colorbar-mid: Midpoint value for color gradient (string, square-root scaled)
        - incident-colorbar-max: Maximum value for color gradient (string, square-root scaled)
        - inspector-card-content: Rendered HTML content showing country-specific incident data

        Callback Inputs:
        - toggle-incident-type n_clicks: Click counter on the toggle button (even/odd determines view)

        Callback State:
        - map-canvas clickInfo: Information about the last clicked country (if any)

        Args:
            n_clicks (int): Click count on the perspective toggle button. Used to determine
                           which perspective is active via modulo 2 operation.
                           - 0, 2, 4, ... (even): Attacker perspective (asking "who attacked whom?")
                           - 1, 3, 5, ... (odd): Receiver perspective (asking "who attacked us?")

            clickInfo (dict | None): Information about the currently selected country from
                                    the map click event. Contains:
                                    - object: Dictionary with 'iso_a2_eh' or
                                      nested 'properties.iso_a2_eh' containing the country code
                                    - None if no country is currently selected

        Returns:
            tuple: Seven-element tuple containing:
                - dict: Base map GeoJSON (output to "base-map-store")
                - list: Arc data for flow visualization (output to "arc-data-store")
                - str: CSS class name for toggle button (output to "toggle-incident-type" className)
                - str: Context label for colorbar (output to "incident-colorbar-context")
                - str: Midpoint value for colorbar (output to "incident-colorbar-mid")
                - str: Maximum value for colorbar (output to "incident-colorbar-max")
                - Component | no_update: Rendered inspector card or no_update
                  (output to "inspector-card-content")

        Raises:
            KeyError: If APP_CACHE structure is missing expected data for the perspective
                     or country combination
            AttributeError: If click_info structure doesn't match expected format

        Side Effects:
            - Triggers updates to multiple dashboard UI components through Dash callback chain
            - May trigger additional callbacks if arc-data-store or base-map-store changes
              trigger other components

        Notes:
            - The callback uses allow_duplicate=True for outputs that may be triggered by
              other callbacks, allowing multiple callbacks to update the same outputs
            - prevent_initial_call=True prevents the callback from running before user
              interaction, optimizing initial load time
            - APP_CACHE must be pre-populated with data for all country/perspective combinations
              for this callback to work correctly
        """
        # Determine which perspective is active by examining the click count parity
        # Even clicks (0, 2, 4, ...): Attacker view | Odd clicks (1, 3, 5, ...): Receiver view
        is_attacker_view = (n_clicks or 0) % 2 == 0

        # Select the incident type enum based on the perspective
        incident_type = (
            static.IncidentType.ATTACKER.value
            if is_attacker_view
            else static.IncidentType.RECEIVER.value
        )

        # Retrieve the maximum incident count for this perspective from the cache
        # This value represents the highest number of incidents in any country for this view
        max_count = APP_CACHE[incident_type]["DEFAULT"]["max_incident_count"]
        mid_count = max_count // 2

        # Set CSS classes to style the toggle button based on the active perspective
        # These classes trigger animations and change the button's visual appearance
        button_class = (
            "floating-toggle-button perspective-toggle is-attacker"
            if is_attacker_view
            else "floating-toggle-button perspective-toggle is-receiver"
        )

        # Create a human-readable label for the colorbar
        # Helps users understand which perspective they're viewing
        colorbar_context = (
            "Attacker perspective" if is_attacker_view else "Receiver perspective"
        )

        # Transform incident counts using square root for better visual scaling
        # This creates a logarithmic-style color gradient that makes differences
        # more visible across the full range of incident counts
        # For example:
        #   If max_count = 100:
        #   - mid_count before: 50 → after: sqrt(50) ≈ 7
        #   - max_count before: 100 → after: sqrt(100) = 10
        # This compression helps distinguish between countries with fewer incidents
        mid_count = str(int((max_count // 2) ** (1 / 2)))
        max_count = str(int(max_count))

        # Handle the case where no country is currently selected on the map
        if clickInfo is None:
            # No country selected, render the default global map view
            # Return data for all countries with no specific country highlighted
            return (
                # GeoJSON base map data (retrieved from cache and formatted for visualization)
                get_map_json_fast(
                    base_geojson=APP_CACHE[incident_type]["DEFAULT"][
                        "base_geojson_dict"
                    ],
                ),
                # Empty arc data (no flows shown when no country is selected)
                [],
                # Button styling
                button_class,
                # Perspective label
                colorbar_context,
                # Scaled midpoint value
                mid_count,
                # Scaled maximum value
                max_count,
                # Don't update the inspector card (no country selected)
                no_update,
            )

        # Extract the ISO Alpha-2 country code from the click event
        iso_alpha_2 = extract_iso_alpha_2(clickInfo)

        # Retrieve the pre-computed inspector card content for this country
        # and perspective combination from the cache
        # The cache contains summary statistics, incident lists, and formatted
        # information about attacks involving this country
        inspector_card_content = APP_CACHE[incident_type][iso_alpha_2][
            "inspector_card_content"
        ]

        # A country is selected: return all data updates including country-specific information
        return (
            # GeoJSON base map data with this country potentially highlighted
            get_map_json_fast(
                base_geojson=APP_CACHE[incident_type]["DEFAULT"]["base_geojson_dict"],
            ),
            # Arc data showing flow lines from/to the selected country based on perspective
            # For attacker view: arrows showing where this country attacked
            # For receiver view: arrows showing who attacked this country
            APP_CACHE[incident_type][iso_alpha_2]["arc_data"],
            # Button styling
            button_class,
            # Perspective label
            colorbar_context,
            # Scaled midpoint value
            mid_count,
            # Scaled maximum value
            max_count,
            # Render the inspector card with country-specific incident data
            render_inspector_card_content(inspector_card_content),
        )
