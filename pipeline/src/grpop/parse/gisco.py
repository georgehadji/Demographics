"""GISCO NUTS boundaries to the map geometry of Greece (ADR 0005, layer L2).

Keeps the Greek regions of one NUTS level from a GISCO GeoJSON snapshot, checks that
they are exactly the codes of data/reference/nuts2024_el.csv, and returns a GeoJSON
FeatureCollection with the source's provenance and licence as foreign members. GISCO's
terms are non-commercial and ask for a credit on every map (registry licence
``gisco_geodata``), so the geometry carries its attribution for the charts to show.
Coordinates are rounded to 4 decimals (about 10 m), far below the 1:3 million scale.
"""

from __future__ import annotations

import json
from typing import Any

from grpop import harmonize
from grpop.snapshots import Snapshot
from grpop.sources.registry import get_source

DECIMALS = 4


def _round(coords: Any) -> Any:
    if isinstance(coords, float | int):
        return round(float(coords), DECIMALS)
    return [_round(c) for c in coords]


def greek_regions(snapshot: Snapshot, raw: bytes, *, level: int) -> dict[str, Any]:
    """The Greek regions of NUTS ``level`` as a GeoJSON FeatureCollection, sorted by code."""
    features = [
        f
        for f in json.loads(raw)["features"]
        if f["properties"]["CNTR_CODE"] == "EL" and f["properties"]["LEVL_CODE"] == level
    ]
    codes = sorted(f["properties"]["NUTS_ID"] for f in features)
    expected = sorted(c for c in harmonize.greek_nuts() if len(c) == 2 + level)
    if codes != expected:
        raise ValueError(f"Greek NUTS {level} regions {codes}, expected {expected}")
    licence = get_source(snapshot.source_id).licence
    if licence == "to_verify":
        raise ValueError(f"{snapshot.source_id}: licence not verified")
    return {
        "type": "FeatureCollection",
        "source": snapshot.source_id,
        "source_url": snapshot.source_url,
        "retrieved_at": snapshot.retrieved_at.isoformat(),
        "licence": licence.name,
        "terms_url": licence.terms_url,
        "commercial_reuse": licence.commercial_reuse,
        "attribution": licence.attribution,
        "features": [
            {
                "type": "Feature",
                "id": f["properties"]["NUTS_ID"],
                "properties": {
                    "geo_code": f["properties"]["NUTS_ID"],
                    "name_latn": f["properties"]["NAME_LATN"],
                },
                "geometry": {
                    "type": f["geometry"]["type"],
                    "coordinates": _round(f["geometry"]["coordinates"]),
                },
            }
            for f in sorted(features, key=lambda f: f["properties"]["NUTS_ID"])
        ],
    }
