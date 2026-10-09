"""Arriaga's decomposition of the change in life expectancy (Δ9i), on recorded tables."""

import polars as pl
import pytest
from test_indicators import data

from grpop import life_expectancy as le


def test_parts_add_up_to_the_change_of_greece():
    df = le.life_expectancy_change(data(le.SOURCES))
    total = df.filter(pl.col("age") == "total")
    groups = df.filter(pl.col("age") != "total")
    sums = groups.group_by("sex", "period").agg(pl.col("value").sum())
    joined = total.join(sums, on=["sex", "period"], suffix="_sum")
    assert (joined["value"] - joined["value_sum"]).abs().max() < 1e-9
    assert set(groups["age"]) == set(le.GROUPS.values())
    # 2023 against 2022 (LIFEXP 81.7 and 80.8, total): mostly the old ages
    t = dict(
        df.filter(pl.col("sex") == "total", pl.col("period") == "2023")
        .select("age", "value")
        .iter_rows()
    )
    assert t["total"] == pytest.approx(0.867, abs=1e-3)
    assert t["65-84"] > t["45-64"] > t["15-44"]


def test_a_change_away_from_eurostats_life_expectancy_stops(monkeypatch):
    read = le._table

    def shifted(d):  # 1% more person-years above every age in 2024: e0 up by ~0.8
        df = read(d)
        return df.with_columns(
            t=pl.when(pl.col("period") == "2024").then(pl.col("t") * 1.01).otherwise("t")
        )

    monkeypatch.setattr(le, "_table", shifted)
    with pytest.raises(ValueError, match="differs from LIFEXP"):
        le.life_expectancy_change(data(le.SOURCES))
