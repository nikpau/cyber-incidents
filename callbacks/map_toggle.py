"""
Map Toggle Callbacks Module
============================

This module handles the interactive map view toggling functionality for the cyber incidents
dashboard. It manages the switching between two complementary perspectives of cyber attack data:
the "attacker perspective" (viewing from the perspective of attack sources) and the
"receiver perspective" (viewing from the perspective of attack targets).

The module registers Dash callbacks that:
1. Toggle between incident perspectives when the user clicks the perspective button
2. Read the currently selected country from the shared state store
3. Update the map visualization, colorbar scaling, and inspector card content
4. Maintain consistent styling and UI state across view changes

Key Concepts:
- Incident Type: An enum (ATTACKER or RECEIVER) determining which perspective is active
- Arc Data: Flow visualization data showing attack origins/destinations between countries
- Colorbar Scale: A square-root-based scaling applied to incident counts for better
  visual representation of attack frequency ranges

Dependencies:
- Dash: For callback registration and reactive updates
- cache: The AppCache instance passed into the callback registration function
- components: Rendering functions for the map visualization and inspector cards
"""

from dash import Dash, Input, Output, State, no_update

from components.inspector_card import (
    render_inspector_card_content,
)
from components.map import get_map_json_fast
from data_helpers.schema import AppCache, IncidentType


def register_perspective_toggle_callbacks(
    cache: AppCache,
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

    @app.callback(
        Output("base-map-store", "data", allow_duplicate=True),
        Output("arc-data-store", "data", allow_duplicate=True),
        Output("toggle-incident-type", "className"),
        Output("incident-colorbar-context", "children"),
        Output("incident-colorbar-mid", "children"),
        Output("incident-colorbar-max", "children"),
        Output("inspector-card-title", "children", allow_duplicate=True),
        Output("inspector-card-image", "src", allow_duplicate=True),
        Output("inspector-card-content", "children", allow_duplicate=True),
        Input("toggle-incident-type", "n_clicks"),
        State("selected-country-store", "data"),
        prevent_initial_call=True,
    )
    def toggle_incident_type(n_clicks: int, selected_country):
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

        7. **Country-Specific Updates**: If a country is selected in the shared state store,
           updates the inspector card to show detailed information about that country's
           incident statistics for the active perspective

        Callback Outputs Explained:
        - base-map-store: GeoJSON data for the base map (same for all perspectives)
        - arc-data-store: Flow visualization data (arrows between countries showing attacks)
        - toggle-incident-type: CSS class name controlling button styling and animations
        - incident-colorbar-context: Text label ("Attacker perspective" or "Receiver perspective")
        - incident-colorbar-mid: Midpoint value for color gradient (string, square-root scaled)
        - incident-colorbar-max: Maximum value for color gradient (string, square-root scaled)
        - inspector-card-title: Title text for the inspector card
        - inspector-card-image: Flag or emblem image for the active country
        - inspector-card-content: Rendered HTML content showing country-specific incident data

        Callback Inputs:
        - toggle-incident-type n_clicks: Click counter on the toggle button (even/odd determines view)

        Callback State:
        - selected-country-store data: The currently selected country code from the dashboard state

        Args:
            n_clicks (int): Click count on the perspective toggle button. Used to determine
                           which perspective is active via modulo 2 operation.
                           - 0, 2, 4, ... (even): Attacker perspective (asking "who attacked whom?")
                           - 1, 3, 5, ... (odd): Receiver perspective (asking "who attacked us?")

            selected_country (str | None): The currently selected country code from the
                                           shared dashboard state. If empty or not present
                                           in the cache for the active perspective, the callback
                                           falls back to the default global view.

        Returns:
            tuple: Nine-element tuple containing:
                - dict: Base map GeoJSON (output to "base-map-store")
                - list: Arc data for flow visualization (output to "arc-data-store")
                - str: CSS class name for toggle button (output to "toggle-incident-type" className)
                - str: Context label for colorbar (output to "incident-colorbar-context")
                - str: Midpoint value for colorbar (output to "incident-colorbar-mid")
                - str: Maximum value for colorbar (output to "incident-colorbar-max")
                - str: Inspector card title text
                - str: Inspector card image source
                - Component | no_update: Rendered inspector card content or no_update
                  (output to "inspector-card-content")

        Raises:
            KeyError: If the cache structure is missing expected data for the selected
                      perspective or country combination.

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
            IncidentType.ATTACKER if is_attacker_view else IncidentType.RECEIVER
        )

        # Retrieve the maximum incident count for this perspective from the cache
        # This value represents the highest number of incidents in any country for this view
        max_count = cache[incident_type]["DEFAULT"]["max_incident_count"]
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
            "Cyber attacks carried out" if is_attacker_view else "Cyber attacks received"
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
        if not selected_country or selected_country not in cache[incident_type]:
            default_inspector_children = no_update
            # No country selected, render the default global map view
            # Return data for all countries with no specific country highlighted
            from components.inspector_card import render_inspector_card_default

            default_inspector_children = render_inspector_card_default().children
            return (
                # GeoJSON base map data (retrieved from cache and formatted for visualization)
                get_map_json_fast(
                    base_geojson=cache[incident_type]["DEFAULT"][
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
                # Default inspector title
                cache[incident_type]["DEFAULT"]["name"],
                # Default inspector image
                cache[incident_type]["DEFAULT"]["svg"],
                # Default inspector body content
                default_inspector_children[2].children,
            )

        # Retrieve the pre-computed inspector card content for this country
        # and perspective combination from the cache
        # The cache contains summary statistics, incident lists, and formatted
        # information about attacks involving this country
        inspector_card_content = cache[incident_type][selected_country][
            "inspector_card_content"
        ]

        # A country is selected: return all data updates including country-specific information
        return (
            # GeoJSON base map data with this country potentially highlighted
            get_map_json_fast(
                base_geojson=cache[incident_type]["DEFAULT"]["base_geojson_dict"],
            ),
            # Arc data showing flow lines from/to the selected country based on perspective
            # For attacker view: arrows showing where this country attacked
            # For receiver view: arrows showing who attacked this country
            cache[incident_type][selected_country]["arc_data"],
            # Button styling
            button_class,
            # Perspective label
            colorbar_context,
            # Scaled midpoint value
            mid_count,
            # Scaled maximum value
            max_count,
            # Country name for selected country
            cache[incident_type][selected_country]["name"],
            # Country image for selected country
            cache[incident_type][selected_country]["svg"],
            # Render the inspector card with country-specific incident data
            render_inspector_card_content(inspector_card_content),
        )
