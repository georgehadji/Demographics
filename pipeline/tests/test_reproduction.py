"""General fertility rate and reproduction rates (Δ9f), on recorded tables."""

import polars as pl
import pytest
from test_indicators import data

from grpop import reproduction as r
from grpop.provenance import AGE_TOTAL, Sex

# UN WPP 2024, Demographic Indicators, medium variant, Greece 2023 (read 2026-10-08)
WPP_NRR, WPP_TFR = 0.6422, 1.3336


@pytest.fixture(scope="module")
def tables():
    d = data(r.SOURCES)
    df = r.reproduction_rates(d)
    rows = df.select("definition_id", "period", "value").iter_rows()
    return d, {(i, p): v for i, p, v in rows}, df


def test_rates_of_greece(tables):
    d, value, df = tables
    births = r._read(r.GIRLS, d).filter(pl.col("age") == AGE_TOTAL, pl.col("period") == "2023")
    girls = dict(births.select("sex", "value").iter_rows())
    share = girls[Sex.FEMALE.value] / girls[Sex.TOTAL.value]
    tfr = value[(r.GRR, "2023")] / share
    assert tfr == pytest.approx(1.2605, abs=1e-4)  # demo_frate summed as TOTFERRT is (1.26)
    nrr = value[(r.NRR, "2023")]
    assert round(nrr, 3) == 0.610
    assert 0.98 < nrr / value[(r.GRR, "2023")] < 1  # few women die before 50
    # the method against WPP: the same ratio to the total fertility rate within 0.5%
    assert nrr / tfr == pytest.approx(WPP_NRR / WPP_TFR, rel=0.005)
    assert 30 < value[(r.GFR, "2023")] < 40
    assert set(df["dataset_code"]) == {
        "demo_fagec+demo_pjan",
        "demo_frate+demo_fasec",
        "demo_frate+demo_fasec+demo_mlifetable",
    }  # ADR 0009


def test_a_year_with_an_age_missing_from_the_life_table_is_left_out(monkeypatch):
    read = r._read

    def without_age_30(series, d):
        df = read(series, d)
        return df.filter(pl.col("age") != "30") if series is r.DYING else df

    monkeypatch.setattr(r, "_read", without_age_30)
    df = r.reproduction_rates(data(r.SOURCES))
    assert df.filter(pl.col("definition_id") == r.NRR).is_empty()
    assert not df.filter(pl.col("definition_id") == r.GRR).is_empty()
