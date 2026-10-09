"""Net migration by age as the cohort residual (Δ9l), on recorded tables."""

import polars as pl
import pytest
from test_indicators import data

from grpop import migration as m
from grpop.indicators import SERIES


@pytest.fixture(scope="module")
def tables():
    d = data(m.SOURCES | {SERIES["immigration"].source_id, SERIES["emigration"].source_id})
    return d, m.net_migration_by_age(d)


def test_ages_add_up_to_net_migration(tables):
    _, df = tables
    total = df.filter(pl.col("age") == "total", pl.col("sex") == "total")
    assert dict(total.select("period", "value").iter_rows()) == {"2023": 29816, "2024": 54135}
    assert set(df["sex"]) == {"total", "male", "female"}
    assert set(df.filter(pl.col("age").str.ends_with("+"))["age"]) == {"100+"}
    assert set(df["dataset_code"]) == {"demo_pjan+demo_mager+demo_fasec"}  # ADR 0009


def test_young_ages_agree_with_the_flows(tables):
    d, df = tables
    key = ["period", "sex", "age"]
    flows = (
        SERIES["immigration"].read(d).join(SERIES["emigration"].read(d), on=key, suffix="_e")
    ).select(*key, flow=pl.col("value") - pl.col("value_e"))
    both = df.join(flows, on=key).with_columns(
        x=pl.col("age").cast(pl.Int32, strict=False), off=(pl.col("value") - pl.col("flow")).abs()
    )
    assert both.filter(pl.col("x") < 50)["off"].max() <= 41
    assert both.filter(pl.col("x") < 70)["off"].max() <= 104
    assert both.filter(pl.col("x") >= 70)["off"].max() > 500  # adjustments (docstring)


def test_a_total_that_differs_from_cnmigrat_fails(tables, monkeypatch):
    d, _ = tables
    read = m.reproduction._read

    def one_more(series, data):
        df = read(series, data)
        return df.with_columns(pl.col("value") + 1) if series is m.NET_MIGRATION else df

    monkeypatch.setattr(m.reproduction, "_read", one_more)
    with pytest.raises(ValueError, match="CNMIGRAT"):
        m.net_migration_by_age(d)
