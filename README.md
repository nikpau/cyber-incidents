# Global Cyber Incidents Dashboard

Interactive geospatial dashboard for exploring transnational cyber incidents from the EuRepoC dataset.

This project visualizes who is attacking whom across countries from 2000 onward, with an emphasis on fast interaction: click a country to reveal incident arcs, switch perspective between attacker and receiver views, and inspect incident-level context in a side panel and modal.

## What This Project Does

- Renders a global country map where each country is colored by incident volume.
- Supports two perspectives:
	- Attacker perspective: cyber attacks carried out by a country.
	- Receiver perspective: cyber attacks received by a country.
- On country click:
	- Draws arc flows between source and destination countries.
	- Updates an inspector card with rankings, threat/target context, and incident summaries.
- On arc click:
	- Opens a detailed modal for the selected incident.
- Includes a reset action to return to the global overview.

The app is optimized for desktop/laptop and intentionally shows a mobile warning overlay on small devices.

## Tech Stack

### Application and UI

- Dash
	- App framework, layout, callback wiring, and client state stores.
- dash-deck + pydeck
	- deck.gl rendering for country polygons and interactive arc layers.
- Plotly
	- Time-series charts inside the inspector card.
- Custom frontend assets
	- CSS and JavaScript in assets for map updates, styling, and UX behavior.

### Data and Geospatial Processing

- DuckDB
	- Primary analytical store for incident records in incidents.duckdb.
- pandas
	- Data shaping, deduplication logic, and incident aggregation.
- GeoPandas + Shapely
	- Country geometry loading, centroid derivation, and antimeridian handling.
- matplotlib
	- Shared color scale generation for country fill and colorbar consistency.

### Runtime and Packaging

- Python 3.12+
- setuptools/pyproject packaging
- gunicorn for production serving
- Docker for containerized deployment

## Data Sources and Dataset Notes

The dashboard is based on EuRepoC cyber incident data. Relevant files in this repository include:

- incidents.duckdb
	- Runtime database used by the app.
- data/eurepoc_dyadic_dataset_0_1.csv
	- Dyadic source table representation where one incident can produce multiple source-target rows.
- data/eurepoc_global_dataset_1_3.csv
- data/eurepoc_attribution_dataset_1.3.csv
- data/eurepoc_receiver_dataset_1.3.csv
- data/map_data/countries.geo.json
	- Country geometries used for map rendering and centroid extraction.

Methodological behavior baked into the app:

- Focuses on dyadic relationships between origin and destination countries.
- Keeps rows with valid ISO alpha-2 country codes for both source and target in mapped flows.
- Excludes non-country destinations such as broad regions and unavailable entries when they cannot be geocoded to specific countries.

## Static Caching Strategy

Performance is driven by a startup precomputation pipeline in cache.py.

At app startup, precompute_app_cache builds an in-memory cache for both perspectives:

- Top-level keys:
	- attacker
	- receiver
- For each perspective:
	- DEFAULT entry containing base map GeoJSON, default inspector metadata, and max incident count.
	- Per-country entries keyed by ISO alpha-2 with:
		- precomputed arc_data
		- precomputed inspector payload
		- country name and country-shape SVG data URI

Why this is fast:

- Heavy database/geospatial work happens once at startup, not on each click.
- Interactive callbacks mostly fetch precomputed structures from memory.
- Map updates are pushed through client-side callback logic for smoother rendering.

Debug cache output:

- python app.py --build-cache writes app_cache.json for inspection/debugging.
- In normal runtime, the app uses the in-memory cache directly.

## Repository Layout

- app.py
	- App bootstrap, layout composition, callback registration, CLI flags.
- cache.py
	- Startup precomputation and cache construction.
- callbacks/
	- map_click.py, map_toggle.py, map_reset.py.
- components/
	- Map canvas, inspector card, plots, and modal components.
- data_helpers/
	- DB access utilities, schema constants, antimeridian fixes.
- assets/
	- CSS and clientside JS used by Dash.
- .github/workflows/docker.yml
	- Container build/push and remote deploy pipeline.

## Local Development Setup

### Prerequisites

- Python 3.12+
- pip

### Install

1. Create and activate a virtual environment.
2. Install the package in editable mode:

	 pip install -e .

### Run the app

Default:

python app.py

Custom host/port:

python app.py --host 0.0.0.0 --port 8050

Debug mode:

python app.py --debug

Precompute and export cache only:

python app.py --build-cache

Then open:

http://127.0.0.1:8050

## Running with Docker

Build:

docker build -t cyber-incidents:local .

Run:

docker run --rm -p 8050:8050 cyber-incidents:local

The container runs gunicorn with preload and two workers, binding to port 8050.

## CI/CD Pipeline

Defined in .github/workflows/docker.yml.

### Trigger conditions

- Automatic on push to main, but only when relevant app files change:
	- source code
	- assets/data
	- Dockerfile
	- workflow file itself
- Manual execution via workflow_dispatch.

### Build and publish stage

1. Checkout repository.
2. Authenticate to GitHub Container Registry (ghcr.io).
3. Generate image metadata and tags:
	 - sha-<commit>
	 - latest (default branch only)
4. Build and push image with Buildx.
5. Use GitHub Actions cache for faster subsequent builds.

Published image naming uses:

- ghcr.io/<owner>/<repo>

For this repository, that resolves to:

- ghcr.io/nikpau/cyber-incidents

### Deployment stage

After successful image push, the deploy job:

1. SSHs into the target server using repository secrets.
2. Logs into GHCR on that server.
3. Changes into an infrastructure directory.
4. Runs docker compose pull for the configured service.
5. Runs docker compose up -d for zero/minimal downtime refresh.
6. Prunes old images.

### Required GitHub Secrets

- DEPLOY_HOST
- DEPLOY_USER
- DEPLOY_SSH_KEY
- DEPLOY_PORT (optional, defaults to 22)
- GHCR_TOKEN
- INFRA_DIR

## Operational Notes

- The app expects incidents.duckdb and data/map_data/countries.geo.json to be present.
- Startup precomputation is intentional and may take a short moment depending on hardware.
- If you are extending callbacks, preserve dcc.Store state contracts:
	- selected-country-store is the source of truth for selected map country.

## Why This Design Works

- Clear separation of concerns:
	- cache precompute phase
	- lean interactive callbacks
	- isolated map/inspector rendering components
- Predictable UI state transitions between global, country-selected, and incident-modal views.
- Container-first deployment with automated GHCR publishing and remote compose rollout.

## Credits

- Data: European Repository of Cyber Incidents (EuRepoC)
- Dashboard implementation: Niklas Paulig
