"""Deviation of earlier projections from the observed population (Δ9e), on recorded tables."""

import polars as pl
import pytest
import test_indicators
from test_indicators import data

from grpop import projection_accuracy as pa


@pytest.fixture
def df(monkeypatch):
    # demo_pjan totals from 2019, the first base year (the shared fixture starts in 2023)
    monkeypatch.setitem(
        test_indicators.RECORDED, "eurostat_demo_pjan", "eurostat_demo_pjan_totals_el_cy.json"
    )
    return pa.projection_accuracy(data(pa.SOURCES))


def value(df, definition_id, dataset_code, period, geo="EL"):
    return df.filter(
        pl.col("definition_id") == definition_id,
        pl.col("dataset_code") == dataset_code,
        pl.col("period") == period,
        pl.col("geo_code") == geo,
    )["value"].item()


def test_deviations_of_europop2019_and_2023(df):
    assert set(df["dataset_code"]) == {"proj_19np+demo_pjan", "proj_23np+demo_pjan"}
    # base year: the revision of the base population, 10,724,599 then, 10,635,213 now
    assert value(df, pa.LEVEL, "proj_19np+demo_pjan", "2019") == pytest.approx(
        100 * (10_724_599 - 10_635_213) / 10_635_213
    )
    # 2025: projected 10,510,196, observed 10,372,335
    level = value(df, pa.LEVEL, "proj_19np+demo_pjan", "2025")
    change = value(df, pa.CHANGE, "proj_19np+demo_pjan", "2025")
    assert level == pytest.approx(100 * (10_510_196 - 10_372_335) / 10_372_335)
    assert change == pytest.approx(
        100 * ((10_510_196 - 10_724_599) - (10_372_335 - 10_635_213)) / 10_635_213
    )
    assert 0 < change < level  # part of the level is the revision of the base
    # no change row in a base year; observed population ends on 1 January 2025
    changes = df.filter(pl.col("definition_id") == pa.CHANGE)
    assert sorted(set(changes["period"])) == ["2020", "2021", "2022", "2023", "2024", "2025"]
    assert df.filter(pl.col("dataset_code") == "proj_23np+demo_pjan")["period"].min() == "2022"
    assert set(df["geo_code"]) == {"EL", "CY"}
