"""Excess mortality (Δ9h): months from weeks, on the recorded weekly deaths of Greece."""

import polars as pl
from test_indicators import data

from grpop import indicators

EXCESS = indicators.INDICATORS["excess_mortality"]


def test_only_months_with_every_day_covered():
    df = indicators.compute(EXCESS, data(indicators.sources(EXCESS)))
    periods = df["period"].to_list()
    assert periods[0] == "2020-01"  # the first month after the 2016-2019 baseline
    # weekly deaths end with 2026-W27 (29 June - 5 July): July is not complete
    assert periods[-1] == "2026-06"
    assert df.filter(pl.col("period") == "2026-06")["status"].item() == "provisional"
