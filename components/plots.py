import plotly.express as px

from static import IncidentType


def plot_incidents_per_year(
    incidents_per_year: dict[int, int], incident_type: IncidentType
) -> px.line:
    """
    Plots a bar chart of the number of incidents per year.

    Args:
        incidents_per_year (dict): A dictionary where keys are years
            and values are the number of incidents in that year.
        incident_type (IncidentType): The type of incident (attacker or receiver).

    Returns:
        plotly.graph_objects.Figure: A bar chart figure representing the number of incidents per year.
    """
    # Convert the dictionary to a list of tuples and sort by year
    sorted_data = sorted(incidents_per_year.items())
    years, counts = zip(*sorted_data) if sorted_data else ([], [])

    title = (
        "Attacks Committed"
        if incident_type == IncidentType.ATTACKER
        else "Attacks Received"
    )

    # Create a line chart using Plotly Express and style it to match the
    # dark inspector-card theme.
    fig = px.line(
        x=years,
        y=counts,
        markers=True,
        labels={"x": "Year", "y": "Number of Incidents"},
        title=title,
    )

    accent_color = "#ef4444" if incident_type == IncidentType.ATTACKER else "#0ea5e9"

    fig.update_traces(
        line=dict(color=accent_color, width=3),
        marker=dict(color=accent_color, size=7),
        hovertemplate=
        "%{y} attacks(s)<extra></extra>",
    )

    fig.update_layout(
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        font=dict(family="Oxanium, sans-serif", color="#f8fafc"),
        title=dict(font=dict(size=16, color="#f8fafc")),
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=dict(size=11, color="#cbd5e1"),
            title_font=dict(size=12, color="#f8fafc"),
            nticks=5,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(148, 163, 184, 0.25)",
            zeroline=False,
            tickfont=dict(size=11, color="#cbd5e1"),
            title_font=dict(size=12, color="#f8fafc"),
        ),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#061527", font=dict(color="#f8fafc"))
    )

    return fig
