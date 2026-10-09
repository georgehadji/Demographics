"""Acceptance tests generated from INDICATORS, on responses recorded from the live API."""

import dataclasses
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from grpop import harmonize, indicators
from grpop.provenance import validate_observations
from grpop.snapshots import Snapshot

FIXTURES = Path(__file__).parent / "fixtures"
# Recorded extract per source id. National: Greece and Cyprus, 2023 onwards for
# demo_pjan, demo_pjanind and demo_pjanbroad, 2021 onwards for the others. Regional:
# EL, EL5 and EL51-EL54, 2024 onwards for the population tables, 2023 for the others;
# demo_r_pjangrp3 also EL511, from 2023.
# An indicator or series whose sources have no entry here fails its tests until one is
# recorded.
RECORDED = {
    "eurostat_demo_pjan": "eurostat_demo_pjan_el_cy.json",
    "eurostat_demo_pjanind": "eurostat_demo_pjanind_el_cy.json",
    "eurostat_demo_gind": "eurostat_demo_gind_el_cy.json",
    "eurostat_demo_find": "eurostat_demo_find_el_cy.json",
    "eurostat_demo_frate": "eurostat_demo_frate_el_cy.json",
    "eurostat_demo_fagec": "eurostat_demo_fagec_el_cy.json",  # 2022-2024
    "eurostat_demo_fasec": "eurostat_demo_fasec_el_cy.json",  # all ages, 2021-2024
    "eurostat_demo_fmonth": "eurostat_demo_fmonth_el_cy.json",  # 1960-2025
    "eurostat_demo_r_mwk_ts": "eurostat_demo_r_mwk_ts_el.json",  # total, 2015-W53 onwards
    "eurostat_demo_mexrt": "eurostat_demo_mexrt_el.json",  # 2020-01 onwards
    "eurostat_demo_mager": "eurostat_demo_mager_el.json",  # 2023-2024
    "eurostat_migr_imm8": "eurostat_migr_imm8_el.json",  # 2023-2024
    "eurostat_migr_emi2": "eurostat_migr_emi2_el.json",  # 2023-2024
    "eurostat_demo_fordagec": "eurostat_demo_fordagec_el_cy.json",  # 2021-2024
    "eurostat_demo_mlexpec": "eurostat_demo_mlexpec_el_cy.json",
    "eurostat_demo_minfind": "eurostat_demo_minfind_el_cy.json",
    "eurostat_demo_nind": "eurostat_demo_nind_el_cy.json",  # 2021-2024
    "eurostat_demo_ndivind": "eurostat_demo_ndivind_el_cy.json",  # 2021-2024
    "eurostat_yth_demo_030": "eurostat_yth_demo_030_el_cy.json",  # 2021-2025
    "eurostat_demo_pjanbroad": "eurostat_demo_pjanbroad_el_cy.json",
    "eurostat_proj_25np": "eurostat_proj_25np_el_cy_pl.json",  # EL, CY, PL; 2025-2026
    "eurostat_proj_19np": "eurostat_proj_19np_el_cy.json",  # totals, 2019-2026
    "eurostat_proj_23np": "eurostat_proj_23np_el_cy.json",  # totals, 2022-2026
    "eurostat_demo_mlifetable": "eurostat_demo_mlifetable_el_cy.json",  # Mx, qx, ex, lx, Tx
    **{
        f"eurostat_demo_r_{code}": f"eurostat_demo_r_{code}_el5.json"
        for code in (
            "d2jan",
            "pjanind2",
            "pjanaggr3",
            "pjangrp3",
            "gind3",
            "find2",
            "mlifexp",
            "minfind",
        )
    },
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


sources = indicators.sources
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
    rows = indicators.disagreements(ind, ours, d)
    assert rows.filter(~pl.col("known") & ~pl.col("corroborated")).is_empty()


@pytest.mark.parametrize("name", list(indicators.SERIES))
def test_series_passes_the_contract(name):
    series = indicators.SERIES[name]
    obs = validate_observations(series.read(data({series.source_id})))
    assert obs.filter(pl.col("geo_code") == "EL")["value"].is_not_null().any()


def test_regional_population_adds_up():
    series = indicators.SERIES["population_regional"]
    obs = series.read(data({series.source_id}))
    assert obs.filter(pl.col("geo_code") == "EL5")["value"].is_not_null().any()
    assert harmonize.hierarchy_gaps(obs).is_empty()


@pytest.mark.parametrize("name", ["sex_ratio", "sex_ratio_regional"])
def test_sex_ratio_is_males_per_100_females(name):
    ind = indicators.INDICATORS[name]
    d = data(sources(ind))
    ours = indicators.compute(ind, d)
    population = ind.inputs["population"].read(d).filter(pl.col("age") == "total")
    for geo, period, value in ours.select("geo_code", "period", "value").iter_rows():
        by_sex = population.filter((pl.col("geo_code") == geo) & (pl.col("period") == period))
        total = {s: v for s, v in by_sex.select("sex", "value").iter_rows()}
        assert value == pytest.approx(100 * total["male"] / total["female"])
    assert set(ours["sex"]) == {"total"} and set(ours["age"]) == {"total"}


def test_life_table_death_rate_and_probability_of_dying_agree():
    """q = m / (1 + m/2) for single years of age, the life table's own relation: it
    fails if the two indicators or the ages are read in the wrong cells."""
    read = {
        n: indicators.SERIES[n].read(data({"eurostat_demo_mlifetable"}))
        for n in ("age_specific_death_rate", "probability_of_dying")
    }
    key = ["geo_code", "period", "sex", "age"]
    both = read["age_specific_death_rate"].join(read["probability_of_dying"], on=key, suffix="_q")
    assert set(both["geo_code"]) == {"EL"}  # Greece only
    age = pl.col("age").cast(pl.Int32, strict=False)  # null for 0-1 classes and 85+, 95+
    single = both.filter(age.is_between(1, 90) & pl.col("value").is_not_null())
    assert single.height > 0
    m, q = single["value"], single["value_q"]
    assert ((q - m / (1 + m / 2)).abs() < 1e-3).all()
    assert set(both.filter(pl.col("age") == "95+")["value_q"].drop_nulls()) == {1.0}


def test_inputs_from_several_sources_are_rejected():
    ind = indicators.INDICATORS["old_age_dependency_ratio"]
    two = dataclasses.replace(ind, inputs={**ind.inputs, "x": indicators.SERIES["net_migration"]})
    with pytest.raises(ValueError, match="one source"):
        indicators.compute(two, data(sources(two)))


def test_disagreement_is_reported():
    ind = indicators.INDICATORS["old_age_dependency_ratio"]
    d = data(sources(ind))
    ours = indicators.compute(ind, d).with_columns(value=pl.col("value") + 0.1)
    assert not indicators.disagreements(ind, ours, d)["known"].any()
    known = dataclasses.replace(ind, known_differences=frozenset({("EL", "2024")}))
    rows = indicators.disagreements(known, ours, d)
    assert rows.filter(pl.col("known"))["geo_code"].unique().to_list() == ["EL"]
    assert set(rows.filter(pl.col("known"))["period"]) == {"2024"}


def test_corroborated_difference_is_explained():
    ind = indicators.INDICATORS["old_age_dependency_ratio"]
    d = data(sources(ind))
    ours = indicators.compute(ind, d).with_columns(value=pl.col("value") + 0.1)
    assert not indicators.disagreements(ind, ours, d)["corroborated"].any()
    (broad,) = ind.corroboration
    bumped = dataclasses.replace(
        broad, formula=lambda i: broad.formula(i).with_columns(value=pl.col("value") + 0.1)
    )
    rows = indicators.disagreements(dataclasses.replace(ind, corroboration=(bumped,)), ours, d)
    assert rows.height > 0
    assert rows["corroborated"].all()


@pytest.mark.parametrize("name", ["old_age_dependency_ratio", "median_age"])
def test_incomplete_ages_are_not_computed(name):
    ind = indicators.INDICATORS[name]
    pop = ind.inputs["population"].read(data(sources(ind)))
    gap = pop.filter(~((pl.col("geo_code") == "EL") & (pl.col("age") == "30")))
    out = ind.formula({"population": gap})
    assert out.filter(pl.col("geo_code") == "EL").is_empty()
    assert not out.filter(pl.col("geo_code") == "CY").is_empty()
