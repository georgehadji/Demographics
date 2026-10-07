"""Total fertility rate by birth order (Δ9b), on recorded tables."""

import polars as pl
import pytest
from test_indicators import data

from grpop import birth_order, indicators


def test_the_orders_add_up_to_eurostat_total_fertility_rate():
    d = data(birth_order.SOURCES)
    df = birth_order.total_fertility_rate_by_order(d)
    total = df.group_by("period").agg(pl.col("value").sum()).sort("period")
    (tfr,) = indicators.INDICATORS["total_fertility_rate"].official  # demo_find TOTFERRT
    official = tfr.read(d).filter(pl.col("geo_code") == "EL")
    joined = total.join(official.select("period", official="value"), on="period")
    assert joined["period"].to_list() == ["2021", "2022", "2023", "2024"]
    assert ((joined["value"] - joined["official"]).abs() <= 0.005 + 37 * 0.5e-5).all()
    assert set(df["dataset_code"]) == {"demo_fordagec+demo_frate"}  # ADR 0009
    assert df.height == 4 * 4


def test_a_mean_age_off_eurostat_stops(monkeypatch):
    monkeypatch.setattr(birth_order, "MEAN_AGE_TOLERANCE", 0.0)
    with pytest.raises(ValueError, match="mean age at birth by order differs"):
        birth_order.total_fertility_rate_by_order(data(birth_order.SOURCES))
