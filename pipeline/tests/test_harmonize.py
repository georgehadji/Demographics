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


def test_nuts_2010_codes_are_recoded_or_dropped(population):
    def at(code, period, value=1.0):
        row = population.filter(pl.col("geo_code") == "EL51")
        return row.with_columns(
            geo_code=pl.lit(code), period=pl.lit(period), value=pl.lit(value, dtype=pl.Float64)
        )

    old = pl.concat([at("EL11", "2011"), at("EL1", "2011"), at("EL111", "2011")])
    old = pl.concat([old, at("EL11", "2012", None), at("EL1", "2012", None)])
    empty_current = at("EL51", "2011", None)
    out = harmonize.recode_nuts2010(pl.concat([empty_current, old]))
    assert out.select("geo_code", "period", "value").rows() == [("EL51", "2011", 1.0)]
    later = at("EL111", "2012")
    assert harmonize.recode_nuts2010(later).height == 1  # kept, so check_greek_codes fails


def test_parent_with_a_missing_child_is_not_compared(population):
    assert harmonize.hierarchy_gaps(population.filter(pl.col("geo_code") != "EL301")).is_empty()


def test_age_groups_add_up_to_the_total():
    from test_indicators import data

    from grpop import build
    from grpop.indicators import SERIES

    obs = SERIES["population_by_age_group_regional"].read(data(["eurostat_demo_r_pjangrp3"]))
    assert {"85+", "85-89", "90+", "unknown"} <= set(obs["age"])
    assert harmonize.age_gaps(obs).is_empty()
    assert set(harmonize.age_gaps(obs, tolerance=-1)["open"]) == {85, 90}  # it compares
    assert harmonize.hierarchy_gaps(obs).is_empty()
    broken = obs.with_columns(
        value=pl.when((pl.col("age") == "90+") & (pl.col("geo_code") == "EL52"))
        .then(pl.col("value") + 7)
        .otherwise("value")
    )
    assert set(harmonize.age_gaps(broken)["open"]) == {90}
    step = build.STEPS["population_by_age_group_regional"]
    with pytest.raises(ValueError, match="age_gaps"):
        build._adds_up(build.Step(step.sources, lambda _: broken)).run({})
