"""Inspector card rendering and cache payload helpers.

This module separates two concerns:
- Build a serializable cache payload from country-level incident data.
- Render Dash HTML components from that payload at interaction time.
"""

import colorsys
from datetime import datetime

import matplotlib.colors as mc
import pandas as pd
from dash import dcc, html

from components.plots import plot_incidents_per_year
from data_helpers.db import ATTACKER_RANKING, RECEIVER_RANKING
from static import DyadicCols, IncidentType


def render_inspector_card_default():
    """Return the default inspector card shown before any country is selected."""
    return html.Div(
        id="floating-inspector-card",
        className="floating-inspector-card",  # Styled via assets/inspector_card.css
        children=[
            html.Img(
                src="/assets/eurepoc_logo.svg",
                alt="Eurepoc logo",
                id="inspector-card-image",
                className="inspector-logo",
            ),
            html.H2(
                id="inspector-card-title",
                children=("Cybercrime Incident Inspector"),
                className="inspector-card-title",
            ),
            html.Div(
                id="inspector-card-content",
                children=[
                    html.P(
                        children=[
                            "This tool uses the ",
                            html.A(
                                "Global Dataset of Cyber Incidents v1.3",
                                href="https://zenodo.org/records/14965395",
                                target="_blank",
                                rel="noopener noreferrer",
                                className="inspector-inline-link",
                            ),
                            " by the European Repository of Cyber Incidents (EuRepoC) to visualize criminal activity in the cyberspace.",
                        ]
                    ),
                    html.P(
                        "EuRepoC recorded"
                    ),
                    html.P(
                        "3146 incidents", className="inspector-card-content-highlight"
                    ),
                    html.P(
                        "in which either state-coordinated or non-state actors were involved in cybercrime incidents across the globe."
                    ),
                    html.P(
                        "Officially, the dataset claims to cover incidents from Jan 1, 2000 to Dec 31, 2024, but I also found incidents from 2025, which is why the title mentions 2000 - 2025."
                    ),
                    html.P(
                        "Click on a country to inspect the arcs of incidents and view country specific information. Use the toggle button to switch between attacker and receiver perspectives."
                    ),
                    html.H3(
                        "Methodology",
                    ),
                    html.P(
                        "This visualization uses the dyadic table of the EuRepoC dataset, which represents each incident as one row per source-target pair. An incident involving N attackers and M targets produces N*M rows. During data pre-processing, I only keep rows where both the source and target countries have valid ISO alpha-2 codes, i.e., only incidents with known countries on both sides are visualized. The EuRepoC dataset also contains incidents with either unknown or broad-region targets (e.g., 'Not available', 'Global', 'Europe', 'Middle East'). These incidents are excluded from the visualization, as they cannot be mapped to a specific country.",
                    ),
                ],
            ),
        ],
    )


def cache_inspector_card_content(
    single_country_info: pd.DataFrame | None,
    incident_type: IncidentType,
) -> list[html.Div | html.P | html.A]:
    """Build a cache-friendly payload for one country and one perspective.

    The payload is plain Python data (dict/list/scalars) so it can be stored in
    app-level cache and later rendered without recomputing database-derived values.

    Payload contains:
    - rank: Global ranking for the country's threat level (1-indexed, or N/A if not ranked)
    - threat_score: Cube-root normalized incident count [0, 1] for bar visualization
    - incident_infos: List of deduplicated incidents involving this country

    Deduplication strategy: Dyadic database may have multiple rows per incident
    (one per source/target pair). We deduplicate by incident id and reconstruct
    the full source/target list from all rows sharing that id.
    """
    cache_payload = {}
    cache_payload["incident_type"] = incident_type

    a_ranks, r_ranks = ATTACKER_RANKING, RECEIVER_RANKING

    a_or_r = "Attacker" if incident_type == IncidentType.ATTACKER else "Receiver"

    # Heading "Attacker Rank:" or "Receiver Rank:"
    cache_payload["rank_heading"] = f"{a_or_r} Rank:"

    # 2-column layout with threat bar on the left and rank on the right
    if single_country_info is not None and not single_country_info.empty:
        # Extract ISO code from first row (all rows for this country have same code).
        a_current_alpha_2 = single_country_info[DyadicCols.INITIATOR_ALPHA_2].iloc[0]
        r_current_alpha_2 = single_country_info[
            DyadicCols.RECEIVER_COUNTRY_ALPHA_2_CODE
        ].iloc[0]

        # Rank lookup: Look up pre-computed global rank for this country.
        # The ranking tables (ATTACKER_RANKING, RECEIVER_RANKING) sort all countries by
        # incident count; countries with no incidents are excluded from the ranking.
        if incident_type == IncidentType.ATTACKER:
            has_rank = a_current_alpha_2 in a_ranks[DyadicCols.INITIATOR_ALPHA_2].values
            if has_rank:
                # Rank is 1-indexed; threat_score is raw incident_count normalized to [0, 1]
                rank = a_ranks.loc[
                    a_ranks[DyadicCols.INITIATOR_ALPHA_2] == a_current_alpha_2
                ]["rank"].item()
                threat_score = (
                    a_ranks.loc[
                        a_ranks[DyadicCols.INITIATOR_ALPHA_2] == a_current_alpha_2,
                        "incident_count",
                    ].item()
                    / a_ranks["incident_count"].max()
                    if a_ranks is not None
                    else 0.0
                )
            else:
                # Country has incidents but didn't make the ranking (usually thresholded)
                rank = None
                threat_score = 0.0
        else:
            # Identical logic for receiver perspective
            has_rank = (
                r_current_alpha_2
                in r_ranks[DyadicCols.RECEIVER_COUNTRY_ALPHA_2_CODE].values
            )
            if has_rank:
                rank = r_ranks.loc[
                    r_ranks[DyadicCols.RECEIVER_COUNTRY_ALPHA_2_CODE]
                    == r_current_alpha_2
                ]["rank"].item()
                threat_score = (
                    r_ranks.loc[
                        r_ranks[DyadicCols.RECEIVER_COUNTRY_ALPHA_2_CODE]
                        == r_current_alpha_2,
                        "incident_count",
                    ].item()
                    / r_ranks["incident_count"].max()
                    if r_ranks is not None
                    else 0.0
                )
            else:
                rank = None
                threat_score = 0.0

        # Cube-root normalization: x^(1/3) compresses the [0, 1] range nonlinearly.
        # Rationale: Raw incident counts are often heavily skewed (e.g., top countries have
        # 100+ incidents, most have <5). Cube-root keeps ordering while spreading lower
        # values across the bar, so the 8-segment threat bar is visually informative even
        # for countries with very few incidents.
        cache_payload["threat_score"] = threat_score ** (1 / 3)
        cache_payload["rank"] = f"#{rank}" if rank is not None else "N/A"
        cache_payload["total_ranks"] = (
            f"/ {len(a_ranks) if incident_type == 'attacker' else len(r_ranks)}"
        )

        # Deduplication: Build one card entry per incident id, collecting all
        # source/target countries from rows sharing that id.
        # Why deduplication is needed: The dyadic table represents each incident as
        # one row per source-target pair. An incident involving N attackers and M targets
        # produces N*M rows. We collapse these back into single incident cards.
        incident_infos = []
        incidents_per_year = {}
        incident_ids_seen = set()
        for _, row in single_country_info.iterrows():
            incident_id = row[DyadicCols.INCIDENT_ID]

            update_incidents_per_year(incidents_per_year, row[DyadicCols.START_DATE])

            if incident_id not in incident_ids_seen:
                incident_ids_seen.add(incident_id)
            else:
                # Skip rows for this incident; we already processed it
                continue

            # Perspective determines what the "opposing side" means:
            # - Attacker view: selected country is source, show targets
            # - Receiver view: selected country is target, show sources
            source_or_target_label = (
                "Source(s)" if incident_type == IncidentType.RECEIVER else "Target(s)"
            )
            # Gather all unique countries on the opposing side for this incident id.
            # Use dropna() + unique() to handle missing/duplicate values in the dyadic table.
            source_or_target_val = (
                ", ".join(
                    single_country_info.loc[
                        single_country_info[DyadicCols.INCIDENT_ID] == incident_id,
                        DyadicCols.INITIATOR_COUNTRY,
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                )
                if incident_type == IncidentType.RECEIVER
                else ", ".join(
                    single_country_info.loc[
                        single_country_info[DyadicCols.INCIDENT_ID] == incident_id,
                        DyadicCols.RECEIVER_COUNTRY,
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                )
            )

            # Determine accent color based on role
            # (attacker = red/orange, receiver = cyan/blue)
            accent_color_class = (
                "incident-card-attacker"
                if incident_type == IncidentType.ATTACKER
                else "incident-card-receiver"
            )

            incident_infos.append(
                {
                    "incident_name": row[DyadicCols.NAME],
                    "incident_date": date_to_human_readable(row[DyadicCols.START_DATE]),
                    "source_or_target_label": source_or_target_label,
                    "source_or_target_val": source_or_target_val,
                    "initiator_name": row[DyadicCols.INITIATOR_NAME],
                    "description": row[DyadicCols.DESCRIPTION],
                    "accent_color_class": accent_color_class,
                }
            )
        # Sort by incident date descending (most recent first) 
        # for display in the inspector card.
        incident_infos.sort(
            key=lambda x: datetime.strptime(x["incident_date"], "%B %d, %Y")
            if x["incident_date"] != "Not available"
            else datetime.min,
            reverse=True,
        )
            
        cache_payload["incident_infos"] = incident_infos
        cache_payload["incidents_per_year"] = incidents_per_year

    # Case: No incidents for the selected country and perspective
    else:
        cache_payload["incident_infos"] = []
        cache_payload["threat_score"] = 0.0
        cache_payload["rank"] = "N/A"

    return cache_payload


def render_inspector_card_content(
    cache_data: dict[str, str],
) -> list[html.Div | html.P | html.A]:
    """Render inspector card components from a precomputed cache payload."""
    # Heading "Attacker Rank:" or "Receiver Rank:"
    rank_heading = html.H2(
        f"{cache_data.get('rank_heading')}",
        className="inspector-card-country-subheading",
    )

    # 2-column layout with threat bar on the left and rank on the right
    if cache_data.get("incident_infos"):
        # Cube root scaling for better visual distribution
        threat_bar = render_threat_bar(
            cache_data.get("threat_score"), cache_data.get("incident_type")
        )

        rank_display = html.Div(
            className="inspector-card-rank-display",
            children=[
                html.H1(
                    f"{cache_data.get('rank')}",
                    className="inspector-card-rank-number",
                ),
                html.P(
                    f"{cache_data.get('total_ranks')}",
                    className="inspector-card-rank-subtext",
                ),
            ],
        )
        
        # Render attacks per year chart if there are incidents per year data
        if cache_data.get("incidents_per_year"):
            incidents_per_year_chart = plot_incidents_per_year(
                cache_data.get("incidents_per_year"), cache_data.get("incident_type")
            )
            incidents_per_year_div = html.Div(
                className="inspector-card-incidents-per-year",
                children=[
                    html.H3(
                        "Incidents Per Year",
                        className="inspector-card-incidents-per-year-title",
                    ),
                    dcc.Graph(
                        figure=incidents_per_year_chart,
                        config={"displayModeBar": False},
                        className="inspector-card-incidents-per-year-graph",
                    ),
                ],
            )

        # Individual incident information cards are collected here and then
        # wrapped in a single expandable container for the whole incident list.
        incident_info_divs = []
        for infodict in cache_data.get("incident_infos"):
            incident_info_divs.append(
                html.Div(
                    className=f"inspector-card-incident-info {infodict.get('accent_color_class')}",
                    children=[
                        # Incident Title
                        html.H3(
                            infodict["incident_name"],
                            className="inspector-card-incident-name",
                        ),
                        # Metadata Grid (2 columns for compact data display)
                        html.Div(
                            className="incident-meta-grid",
                            children=[
                                html.Div(
                                    className="meta-item",
                                    children=[
                                        html.Span("Date", className="meta-label"),
                                        html.Span(
                                            f"{infodict['incident_date']}",
                                            className="meta-value",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="meta-item",
                                    children=[
                                        html.Span(
                                            infodict["source_or_target_label"],
                                            className="meta-label",
                                        ),
                                        html.Span(
                                            infodict["source_or_target_val"],
                                            className="meta-value",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="meta-item",
                                    children=[
                                        html.Span("Initiator", className="meta-label"),
                                        html.Span(
                                            f"{infodict['initiator_name']}",
                                            className="meta-value",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        # Description spanning full width
                        html.Div(
                            className="incident-description-container",
                            children=[
                                html.Details(
                                    children=[
                                        html.Summary(
                                            "Description",
                                            className="meta-label incident-description-toggle",
                                        ),
                                        html.P(
                                            f"{infodict['description']}",
                                            className="inspector-card-incident-description",
                                        ),
                                    ]
                                ),
                            ],
                        ),
                    ],
                )
            )

        incident_section = html.Details(
            className="incident-list-card",
            children=[
                html.Summary(
                    "Click to see individual incidents",
                    className="meta-label incident-list-toggle",
                ),
                html.Div(className="incident-list-content", children=incident_info_divs),
            ],
        )
    else:
        incident_section = html.P(
            "No recorded incidents in the dataset for this country and perspective.",
            className="inspector-card-no-incidents",
        )
        threat_bar = render_threat_bar(0.0, cache_data.get("incident_type"))
        rank_display = html.Div(
            className="inspector-card-rank-display",
            children=[
                html.H1("N/A", className="inspector-card-rank-number"),
            ],
        )
        incidents_per_year_div = html.Div()

    return [
        rank_heading,
        html.Div(
            className="inspector-card-rank-container",
            children=[threat_bar, rank_display],
        ),
        incidents_per_year_div,
        incident_section,
    ]

def update_incidents_per_year(incidents_per_year: dict[int, int], start_date: str):
    """In place update the incidents_per_year dictionary 
    with the year extracted from start_date.
    """
    try:
        year = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S").year
        if year in incidents_per_year:
            incidents_per_year[year] += 1
        else:
            incidents_per_year[year] = 1
    except ValueError:
        # Handle cases where start_date is not in the expected format
        pass

def render_threat_bar(score: float, incident_type: IncidentType) -> html.Div:
    """Render a segmented threat/importance bar for a normalized score in [0, 1].

    The bar has 8 segments, each representing a threshold at i/8 (0, 0.125, 0.25, ...).
    Segments are colored green → yellow → red as score increases, reflecting threat level.
    For receiver view, the label changes to "Target Importance" (strategic value).
    """
    cmap = [
        "#048757",
        "#36a35f",
        "#67bf67",
        "#9cdb97",
        "#ff8787",
        "#f04242",
        "#d42929",
        "#b62b2b",
    ]
    bars = []
    num_bars = len(cmap)
    for i in range(num_bars):
        bar_color = cmap[i]
        # Segment fill threshold: each step lights up once score crosses i/num_bars.
        if not score > (i / num_bars):
            bar_color = "#696969"  # Darken the color for unfilled bars
        bars.append(
            html.Div(
                style={
                    "background-color": bar_color,
                    "height": "20px",
                    "width": "10px",
                    "margin": "0 2px",
                    "transition": "background-color 0.3s ease",
                },
            )
        )
    threat_bar_name = html.Div(
        "Threat Level"
        if incident_type == IncidentType.ATTACKER
        else "Target Importance",
        className="inspector-card-threat-bar-name",
    )
    return html.Div(
        className="inspector-card-threat-bar-container",
        children=[
            html.Div(className="inspector-card-threat-bar", children=bars),
            threat_bar_name,
        ],
    )


def lighten_or_darken_color(color: str, amount: float) -> str:
    """Return a lightened/darkened color by scaling luminance in HLS space."""
    try:
        c = mc.cnames[color]
    except KeyError:
        c = color
    c = colorsys.rgb_to_hls(*mc.to_rgb(c))
    r, g, b = colorsys.hls_to_rgb(c[0], 1 - amount * (1 - c[1]), c[2])
    return mc.to_hex((r, g, b))


def date_to_human_readable(date_str: str) -> str:
    """Format database datetime strings as "Month DD, YYYY"; fallback to input."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return date_obj.strftime("%B %d, %Y")
    except ValueError:
        return date_str  # Return the original string if parsing fails
