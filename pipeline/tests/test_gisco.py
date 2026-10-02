from datetime import UTC, datetime
from pathlib import Path

import pytest

from grpop import harmonize
from grpop.parse import gisco
from grpop.snapshots import Snapshot
from grpop.sources.registry import get_source

RAW = (Path(__file__).parent / "fixtures" / "gisco_nuts2_handwritten.geojson").read_bytes()
SNAP = Snapshot(
    "0" * 64,
    "gisco_nuts2_2024_geo",
    "https://example.org/x",
    datetime(2026, 10, 2, tzinfo=UTC),
    len(RAW),
)


def test_keeps_the_greek_regions_sorted_with_provenance_and_licence():
    doc = gisco.greek_regions(SNAP, RAW, level=2)
    codes = [f["id"] for f in doc["features"]]
    assert codes == sorted(c for c in harmonize.greek_nuts() if len(c) == 4)
    assert doc["features"][0]["properties"] == {"geo_code": "EL30", "name_latn": "Region EL30"}
    licence = get_source("gisco_nuts2_2024_geo").licence
    assert doc["attribution"] == licence.attribution
    assert doc["commercial_reuse"] is False
    assert doc["retrieved_at"] == "2026-10-02T00:00:00+00:00"


def test_rounds_coordinates_to_four_decimals():
    ring = gisco.greek_regions(SNAP, RAW, level=2)["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == [22.1235, 38.6543]


def test_a_missing_region_fails():
    raw = RAW.replace(b'"EL43"', b'"EL99"')
    with pytest.raises(ValueError, match="Greek NUTS 2 regions"):
        gisco.greek_regions(SNAP, raw, level=2)
