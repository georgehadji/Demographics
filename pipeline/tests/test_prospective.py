"""Prospective old-age dependency (Δ9d), on recorded tables."""

import polars as pl
from test_indicators import data

from grpop import prospective
from grpop.indicators import SERIES


def test_thresholds_and_ratio_on_recorded_tables():
    d = data(prospective.SOURCES)
    df = prospective.prospective_old_age_dependency(d)
    limit = dict(
        df.filter(pl.col("definition_id") == prospective.THRESHOLD, pl.col("period") == "2024")
        .select("sex", "value")
        .iter_rows()
    )
    assert 60 < limit["male"] < limit["female"] < 80  # women live longer
    ratio = df.filter(pl.col("definition_id") == prospective.RATIO)
    assert ratio["period"].to_list() == ["2023", "2024"]  # 1 January 2025 is the last
    assert set(ratio["dataset_code"]) == {"demo_pjan+demo_mlifetable"}  # ADR 0009
    # the threshold is above 65 for both sexes, so the ratio is below 65+ per 20-64
    pop = (
        SERIES["population"]
        .read(d)
        .filter(pl.col("geo_code") == "EL", pl.col("period") == "2024", pl.col("sex") == "total")
    )
    x = pop["age"].str.strip_suffix("+").cast(pl.Int32, strict=False)
    old = pop.filter(x >= 65)["value"].sum() / pop.filter((x >= 20) & (x < 65))["value"].sum()
    assert ratio.filter(pl.col("period") == "2024")["value"][0] < 100 * old
