import colorsys
from datetime import datetime

import matplotlib.colors as mc
import pandas as pd
from dash import html

from data_helpers.db import ATTACKER_RANKING, RECEIVER_RANKING
from static import DyadicCols, IncidentType


def render_inspector_card_default():
    """Renders the floating overlay card component."""
    return html.Div(
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
                            " by the European Repository of Cyber Incidents (EuRepoC) to visualize criminal activity in cyberspace.",
                        ]
                    ),
                    html.P(
                        "Between January 1, 2000 and December 31, 2024, EuRepoC recorded"
                    ),
                    html.P(
                        "3146 incidents", className="inspector-card-content-highlight"
                    ),
                    html.P(
                        "in which either state-coordinated or non-state actors were involved in cybercrime incidents across the globe."
                    ),
                    html.P(
                        "Click on a country to inspect the arcs of incidents and view country specific information. Use the toggle button to switch between attacker and receiver perspectives."
                    ),
                ],
            ),
        ],
    )


def cache_inspector_card_content(
    single_country_info: pd.DataFrame | None,
    incident_type: IncidentType,
) -> list[html.Div | html.P | html.A]:
    """
    Caches the content of the inspector card for a specific country and incident type
    into a dictionary of strings.
    """
    cache_payload = {}
    cache_payload["incident_type"] = incident_type

    a_ranks, r_ranks = ATTACKER_RANKING, RECEIVER_RANKING

    a_or_r = "Attacker" if incident_type == IncidentType.ATTACKER else "Receiver"

    # Heading "Attacker Rank:" or "Receiver Rank:"
    cache_payload["rank_heading"] = f"{a_or_r} Rank:"

    # 2-column layout with threat bar on the left and rank on the right
    if single_country_info is not None and not single_country_info.empty:
        a_current_alpha_2 = single_country_info[DyadicCols.INITIATOR_ALPHA_2].iloc[0]
        r_current_alpha_2 = single_country_info[
            DyadicCols.RECEIVER_COUNTRY_ALPHA_2_CODE
        ].iloc[0]

        if incident_type == IncidentType.ATTACKER:
            has_rank = a_current_alpha_2 in a_ranks[DyadicCols.INITIATOR_ALPHA_2].values
            if has_rank:
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
                rank = None
                threat_score = 0.0
        else:
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

        # Cube root scaling for better visual distribution
        cache_payload["threat_score"] = threat_score ** (1 / 3)
        cache_payload["rank"] = f"#{rank}" if rank is not None else "N/A"
        cache_payload["total_ranks"] = (
            f"/ {len(a_ranks) if incident_type == 'attacker' else len(r_ranks)}"
        )

        # Individual indicent information:
        incident_infos = []
        incident_ids_seen = set()  # To avoid duplicates
        for _, row in single_country_info.iterrows():
            incident_id = row[DyadicCols.INCIDENT_ID]

            if incident_id not in incident_ids_seen:
                incident_ids_seen.add(incident_id)
            else:
                continue

            source_or_target_label = (
                "Source(s)" if incident_type == IncidentType.RECEIVER else "Target(s)"
            )
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
        cache_payload["incident_infos"] = incident_infos

    # Case: No incidents for the selected country and perspective
    else:
        cache_payload["incident_infos"] = []
        cache_payload["threat_score"] = 0.0
        cache_payload["rank"] = "N/A"

    return cache_payload


def render_inspector_card_content(
    cache_data: dict[str, str],
) -> list[html.Div | html.P | html.A]:
    """
    Renders the content of the inspector card based on cached data.

    Args:
        cache_data (dict[str, str]): A dictionary containing cached content for the inspector card.

    Returns:
        list: A list of Dash HTML components representing the content of the inspector card.
    """
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

        # Individual indicent information:
        # One Div with the "name" as the heading,
        # Target/Source country/countries ("initiator_country" or "receiver_country"),
        # Incident date ("start_date")
        # Initiator ("initiator_name")
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
    else:
        incident_info_divs = [
            html.P(
                "No recorded incidents in the dataset for this country and perspective.",
                className="inspector-card-no-incidents",
            )
        ]
        threat_bar = render_threat_bar(0.0, cache_data.get("incident_type"))
        rank_display = html.Div(
            className="inspector-card-rank-display",
            children=[
                html.H1("N/A", className="inspector-card-rank-number"),
            ],
        )

    return [
        rank_heading,
        html.Div(
            className="inspector-card-rank-container",
            children=[threat_bar, rank_display],
        ),
        *incident_info_divs,
    ]


def render_threat_bar(score: float, incident_type: IncidentType) -> html.Div:
    """
    Renders a threat bar component based on the given score.

    Args:
        score (float): The threat score for the country, ranging from 0 to 1.
        incident_type (IncidentType): The type of incident (attacker or receiver).

    Returns:
        html.Div: A Dash HTML Div component representing the threat bar.
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
    """
    Lightens or darkens a color by a specified amount.
    Proudly borrowed from https://stackoverflow.com/questions/37765197/darken-or-lighten-a-color-in-matplotlib

    Args:
        color (str): The color (string, hexcode, RGB tuple) to be lightened or darkened.
        amount (float): The amount to lighten or darken the color.
        Values greater than 1 will darken the color, while values
        between 0 and 1 will lighten it.

    Returns:
        str: The modified hex color code.
    """
    try:
        c = mc.cnames[color]
    except KeyError:
        c = color
    c = colorsys.rgb_to_hls(*mc.to_rgb(c))
    r, g, b = colorsys.hls_to_rgb(c[0], 1 - amount * (1 - c[1]), c[2])
    return mc.to_hex((r, g, b))


def date_to_human_readable(date_str: str) -> str:
    """
    Converts a date string in the format 'YYYY-MM-DD' to a human-readable format like 'January 1, 2024'.

    Args:
        date_str (str): The date string in 'YYYY-MM-DD' format.

    Returns:
        str: The date in a human-readable format, e.g., 'January 1, 2024'.
    """
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return date_obj.strftime("%B %d, %Y")
    except ValueError:
        return date_str  # Return the original string if parsing fails
