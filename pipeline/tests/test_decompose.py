"""The change in births split into women and fertility (Δ9a), on recorded tables."""

import polars as pl
from test_indicators import RECORDED, data

from grpop import decompose
from grpop.indicators import Series
from grpop.provenance import Nature


def test_the_parts_add_up_to_the_change_in_eurostat_births():
    df = decompose.births_change(data(decompose.SOURCES))
    total = df.filter(pl.col("age") == "total").group_by("period").agg(pl.col("value").sum())
    births = Series(
        "eurostat_demo_gind", "live_births@v1", Nature.OFFICIAL_ESTIMATE, {"indic_de": "LBIRTH"}
    ).read(data({"eurostat_demo_gind"}))
    el = dict(births.filter(pl.col("geo_code") == "EL").select("period", "value").iter_rows())
    (period, value), *rest = total.iter_rows()  # births and mean women meet in 2023-2024 only
    assert (period, rest) == ("2024", [])
    assert abs(value - (el["2024"] - el["2023"])) < 1e-6
    assert set(df["dataset_code"]) == {"demo_fagec+demo_pjan"}  # ADR 0009, numerator first
    assert set(df["nature"]) == {"derived"}
    assert df.filter(pl.col("age") != "total").height == 2 * len(decompose.CLASSES)
    assert "eurostat_demo_fagec" in RECORDED
