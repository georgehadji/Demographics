from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from grpop import harmonize, snapshots
from grpop.parse import eurostat
from grpop.provenance import Nature

# Recorded from the live API: demo_r_pjanaggr3, all 70 Greek codes, sex T, age TOTAL, 2025.
FIXTURE = Path(__file__).parent / "fixtures" / "eurostat_demo_r_pjanaggr3_el_2025.json"


@pytest.fixture
def population(tmp_path):
    data = FIXTURE.read_bytes()
    snap = snapshots.put(
        tmp_path,
        data,
        source_id="eurostat_demo_r_pjanaggr3",
        source_url="https://example.org/x",
        retrieved_at=datetime(2026, 9, 29, tzinfo=UTC),
    )
    return eurostat.to_observations(
        snap,
        data,
        definition_id="population_1jan@v1",
        nature=Nature.OFFICIAL_ESTIMATE,
        geo_vintage="NUTS2024",
    )


def test_reference_has_every_greek_level():
    lengths = sorted(len(c) for c in harmonize.greek_nuts())
    assert [lengths.count(n) for n in (2, 3, 4, 5)] == [1, 4, 13, 52]


def test_real_greek_data_uses_current_codes_and_adds_up(population):
    assert population.height == 70
    harmonize.check_greek_codes(population)
    assert harmonize.hierarchy_gaps(population).is_empty()


def test_nuts_2010_code_is_rejected(population):
    old = population.with_columns(geo_code=pl.lit("EL11"))
    with pytest.raises(ValueError, match="EL11"):
        harmonize.check_greek_codes(old)


def test_gap_is_reported_at_the_parent(population):
    broken = population.with_columns(
        value=pl.when(pl.col("geo_code") == "EL301").then(0.0).otherwise(pl.col("value"))
    )
    assert harmonize.hierarchy_gaps(broken)["geo_code"].to_list() == ["EL30"]
