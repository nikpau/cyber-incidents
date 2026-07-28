"""Utilities for repairing map geometries that tear at the antimeridian.

Why this module exists
----------------------
Country polygons are commonly stored in longitude/latitude degrees where
longitudes are normalized to the range [-180, 180]. For countries that cross
the International Date Line (the antimeridian), that representation can make a
single contiguous country look like it has a huge jump across the map canvas.

In interactive map rendering, this often appears as:
- long polygon edges that stretch across the world,
- country fills that leak through the opposite hemisphere,
- click/hover hit areas that are visually offset.

This module applies a pragmatic rendering-time fix by shifting only the
"spillover" coordinates by +/- 360 degrees so each affected country becomes
locally contiguous for plotting.
"""

from shapely.ops import transform
import geopandas as gpd


def fix_antimeridian_tearing(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
        Repair geometries that visually tear at the antimeridian.

        This function scans each geometry's bounding box and identifies very wide
        shapes as candidates for Date Line crossing. For those candidates, it uses
        the geometry centroid to infer the primary hemisphere, then shifts only the
        opposite-side spillover coordinates by +/- 360 degrees.

        Parameters
        ----------
        gdf:
                A GeoDataFrame in geographic longitude/latitude coordinates
                (EPSG:4326) with a valid ``geometry`` column.

        Returns
        -------
        geopandas.GeoDataFrame
                A copy of the input GeoDataFrame where candidate antimeridian-crossing
                geometries are transformed to render contiguously on standard map
                projections. Non-crossing geometries are returned unchanged.

        Algorithm overview
        ------------------
        1. Iterate through geometries and skip null/empty records.
        2. Compute bounds ``(minx, miny, maxx, maxy)``.
        3. If width ``(maxx - minx) > 270``, treat geometry as crossing the Date
             Line. The wide threshold avoids false positives from typical countries
             and catches split geometries near +/-180.
        4. Use centroid longitude to choose dominant hemisphere:
             - centroid > 0 (eastern): shift far-west spillover coordinates east
                 (``x < -90`` -> ``x + 360``)
             - centroid <= 0 (western): shift far-east spillover coordinates west
                 (``x > 90`` -> ``x - 360``)

        Notes and assumptions
        ---------------------
        - This is a display-oriented normalization, not a geodetic/topology repair.
        - Thresholds (270 for width, +/-90 for spillover) are heuristic and tuned
            for world-country polygons in the current dataset.
        - Antarctica and other polar-edge cases may exceed width thresholds for
            reasons unrelated to antimeridian crossing.
        - The function preserves Z values when present.
    """
    fixed_gdf = gdf.copy()

        # Shift far-western spillover to the eastern side, keeping the shape local.
    def shift_east(x, y, z=None):
        new_x = x + 360 if x < -90 else x
        return (new_x, y) if z is None else (new_x, y, z)

        # Shift far-eastern spillover to the western side, keeping the shape local.
    def shift_west(x, y, z=None):
        new_x = x - 360 if x > 90 else x
        return (new_x, y) if z is None else (new_x, y, z)

    for idx, row in fixed_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        minx, miny, maxx, maxy = geom.bounds

        # If the bounding box is > 270 degrees wide, it crosses the Date Line.
        # We should maybe ignore Antarctica (AQ) because it 
        # legitimately circles the South Pole, but we leave it for now
        if (maxx - minx) > 270:

            # Use centroid to determine the country's primary hemisphere
            if geom.centroid.x > 0:
                # Country is mostly in the Eastern Hemisphere (e.g., Russia)
                # Shift its negative spillover to the positive side.
                fixed_gdf.at[idx, 'geometry'] = transform(shift_east, geom)
            else:
                # Country is mostly in the Western Hemisphere (e.g., USA)
                # Shift its positive spillover to the negative side.
                fixed_gdf.at[idx, 'geometry'] = transform(shift_west, geom)

    return fixed_gdf