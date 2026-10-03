"""EUROPOP2025 on a recorded extract of proj_25np (EL, CY and PL, 2025-2026)."""

import polars as pl
import pytest
from test_indicators import data

from grpop import projections
from grpop.indicators import SERIES

DATA = data([projections.SOURCE, "eurostat_demo_pjan"])


@pytest.fixture(scope="module")
def projected():
    return projections.read(DATA)


def test_baseline_is_projected_and_each_sensitivity_test_a_scenario(projected):
    by = projected.group_by("nature", "scenario_id").len()
    assert set(by["scenario_id"].drop_nulls()) == set(projections.SCENARIOS.values())
    assert by.filter(pl.col("scenario_id").is_null())["nature"].to_list() == ["projected"]
    assert set(projected["interval"].drop_nulls()) == set()
    assert set(projected["age"]) >= {"total", "0", "99", "100+", "65+"}


def test_greece_base_year_equals_the_observed_population(projected):
    totals = projections.totals(projected, SERIES["population"].read(DATA))
    el = totals.filter(
        (pl.col("geo_code") == "EL")
        & (pl.col("period") == "2025")
        & pl.col("scenario_id").is_null()
    )
    assert el["value"].to_list() == [10372335]
    assert set(totals["age"]) == {"total"} and set(totals["sex"]) == {"total"}


def test_an_unexplained_or_vanished_base_year_difference_stops_the_build(projected, monkeypatch):
    observed = SERIES["population"].read(DATA)
    shifted = observed.with_columns(value=pl.col("value") + 1)
    with pytest.raises(ValueError, match=r"unexplained differences \['CY', 'EL'\]"):
        projections.totals(projected, shifted)
    monkeypatch.setattr(projections, "KNOWN_BASE_DIFFERENCES", frozenset({"EL"}))
    with pytest.raises(ValueError, match=r"listed differences gone \['EL'\]"):
        projections.totals(projected, observed)


def test_an_unknown_projection_type_raises(monkeypatch):
    monkeypatch.delitem(projections.SCENARIOS, "DCONV")
    with pytest.raises(ValueError, match="unknown projection types"):
        projections.read(DATA)
