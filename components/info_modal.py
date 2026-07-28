"""Incident info modal shown for a selected incident arc."""

from dash import html

from components.inspector_card import render_threat_bar
from static import IncidentType


def render_incident_info_modal(
    inspector_card_content: dict,
    incident_arc_name: str,
    country_name: str,
    image_uri: str,
    incident_type: IncidentType,
) -> html.Div:
    """Render a large, inspector-card-styled modal for a selected incident."""
    incident_infos: list[dict] = inspector_card_content.get("incident_infos", [])

    selected_incident_info = next(
        (
            info
            for info in incident_infos
            if info.get("incident_name") == incident_arc_name
        ),
        None,
    )

    rank = inspector_card_content.get("rank", "N/A")
    total_ranks = inspector_card_content.get("total_ranks", "")
    threat_score = inspector_card_content.get("threat_score", 0.0)

    incident_name = (
        selected_incident_info.get("incident_name")
        if selected_incident_info is not None
        else "Selected incident"
    )
    description = (
        selected_incident_info.get("description")
        if selected_incident_info is not None
        else "No description available for this incident."
    )
    incident_date = (
        selected_incident_info.get("incident_date")
        if selected_incident_info is not None
        else "Not available"
    )
    counterpart_label = (
        selected_incident_info.get("source_or_target_label")
        if selected_incident_info is not None
        else "Target(s)"
    )
    counterpart_value = (
        selected_incident_info.get("source_or_target_val")
        if selected_incident_info is not None
        else "Not available"
    )
    initiator_name = (
        selected_incident_info.get("initiator_name")
        if selected_incident_info is not None
        else "Not available"
    )

    country_name_display = (
        f"Attack on {country_name}"
        if incident_type == IncidentType.RECEIVER
        else f"Attack from {country_name}"
    )

    return html.Div(
        className="incident-info-modal-overlay",
        children=[
            html.Div(
                className="incident-info-modal",
                children=[
                    html.Div(
                        className="incident-info-modal-header",
                        children=[
                            html.Div(
                                className="incident-info-modal-heading",
                                children=[
                                    html.H2(
                                        country_name_display,
                                        className="incident-info-modal-title",
                                    ),
                                    html.Div(
                                        className="incident-info-modal-rank-pill",
                                        children=[
                                            html.Span(
                                                "Rank",
                                                className="meta-label",
                                            ),
                                            html.H1(
                                                f"{rank} {total_ranks}",
                                                className="inspector-card-rank-number incident-info-modal-rank-number",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="incident-info-modal-threat-card",
                                        children=[
                                            render_threat_bar(
                                                threat_score, incident_type
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="incident-info-modal-flag-card",
                                children=[
                                    html.Img(
                                        src=image_uri or "/assets/eurepoc_logo.svg",
                                        alt=f"{country_name} outline",
                                        className="incident-info-modal-flag",
                                    )
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="incident-info-modal-body",
                        children=[
                            html.Div(
                                className="incident-info-modal-description-card",
                                children=[
                                    html.H3(
                                        incident_name,
                                        className="inspector-card-incident-name",
                                    ),
                                    html.Span(
                                        "Description",
                                        className="meta-label",
                                    ),
                                    html.Div(
                                        className="incident-info-modal-metadata-grid",
                                        children=[
                                            html.Div(
                                                className="incident-info-modal-meta-item",
                                                children=[
                                                    html.Span(
                                                        "Date",
                                                        className="meta-label",
                                                    ),
                                                    html.Span(
                                                        incident_date,
                                                        className="meta-value",
                                                    ),
                                                ],
                                            ),
                                            html.Div(
                                                className="incident-info-modal-meta-item",
                                                children=[
                                                    html.Span(
                                                        counterpart_label,
                                                        className="meta-label",
                                                    ),
                                                    html.Span(
                                                        counterpart_value,
                                                        className="meta-value",
                                                    ),
                                                ],
                                            ),
                                            html.Div(
                                                className="incident-info-modal-meta-item",
                                                children=[
                                                    html.Span(
                                                        "Initiator",
                                                        className="meta-label",
                                                    ),
                                                    html.Span(
                                                        initiator_name,
                                                        className="meta-value",
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    html.P(
                                        description,
                                        className="inspector-card-incident-description incident-info-modal-description",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            )
        ],
    )
