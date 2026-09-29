"""Acceptance tests generated from INDICATORS, on responses recorded from the live API."""

import dataclasses
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from grpop import indicators
from grpop.snapshots import Snapshot

FIXTURES = Path(__file__).parent / "fixtures"
# Recorded extract per source id (Greece and Cyprus, 2023 onwards). An indicator whose
# sources have no entry here fails its acceptance test until one is recorded.
RECORDED = {
    "eurostat_demo_pjan": "eurostat_demo_pjan_el_cy.json",
    "eurostat_demo_pjanind": "eurostat_demo_pjanind_el_cy.json",
}


def data(source_ids):
    out = {}
    for source_id in source_ids:
        raw = (FIXTURES / RECORDED[source_id]).read_bytes()
        snap = Snapshot(
            hashlib.sha256(raw).hexdigest(),
            source_id,
            "https://example.org/x",
            datetime(2026, 9, 29, tzinfo=UTC),
            len(raw),
        )
        out[source_id] = (snap, raw)
    return out


def sources(ind):
    series = [*ind.inputs.values(), *ind.official]
    return {s.source_id for s in series}


WITH_OFFICIAL = [name for name, ind in indicators.INDICATORS.items() if ind.official]


@pytest.mark.parametrize("name", list(indicators.INDICATORS))
def test_indicator_output_passes_the_contract(name):
    ind = indicators.INDICATORS[name]
    ours = indicators.compute(ind, data(sources(ind)))
    assert ours.height > 0
    assert set(ours["nature"]) == {"derived"}


@pytest.mark.parametrize("name", WITH_OFFICIAL)
def test_indicator_agrees_with_official_value(name):
    ind = indicators.INDICATORS[name]
    d = data(sources(ind))
    ours = indicators.compute(ind, d)
    compared = ours.join(indicators.read_official(ind, d), on=indicators.KEY)
    assert compared.height > 0, "nothing to compare"
    assert indicators.disagreements(ind, ours, d).filter(~pl.col("known")).is_empty()


def test_disagreement_is_reported():
    ind = indicators.INDICATORS["old_age_dependency_ratio"]
    d = data(sources(ind))
    ours = indicators.compute(ind, d).with_columns(value=pl.col("value") + 0.1)
    assert not indicators.disagreements(ind, ours, d)["known"].any()
    known = dataclasses.replace(ind, known_differences=frozenset({("EL", "2024")}))
    rows = indicators.disagreements(known, ours, d)
    assert rows.filter(pl.col("known"))["geo_code"].unique().to_list() == ["EL"]
    assert set(rows.filter(pl.col("known"))["period"]) == {"2024"}


@pytest.mark.parametrize("name", ["old_age_dependency_ratio", "median_age"])
def test_incomplete_ages_are_not_computed(name):
    ind = indicators.INDICATORS[name]
    pop = ind.inputs["population"].read(data(sources(ind)))
    gap = pop.filter(~((pl.col("geo_code") == "EL") & (pl.col("age") == "30")))
    out = ind.formula({"population": gap})
    assert out.filter(pl.col("geo_code") == "EL").is_empty()
    assert not out.filter(pl.col("geo_code") == "CY").is_empty()
