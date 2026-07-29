FROM python:3.12-slim

# ----- System dependencies ----------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ----- Python dependencies ----------------------------------------------------
# Copy only the package manifest first so the dependency layer is cached
# independently from source-code changes.
COPY pyproject.toml .
COPY assets/ assets/
COPY callbacks/ callbacks/
COPY components/ components/
COPY data_helpers/ data_helpers/
COPY app.py .
COPY incidents.duckdb .
COPY cache.py .

# Install the package and all dependencies declared in pyproject.toml.
RUN pip install --no-cache-dir .

# ── Runtime ───────────────────────────────────────────────────────────────────
EXPOSE 8050

# Run FastAPI on port 8050.
CMD ["gunicorn", "app:server", "--workers", "2", "--preload", "--bind", "0.0.0.0:8050"]
