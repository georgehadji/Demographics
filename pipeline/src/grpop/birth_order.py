"""Total fertility rate by birth order (Δ9b): first, second, third, fourth and later.

Eurostat publishes the age-specific fertility rates (demo_frate) and the births by
mother's age and birth order (demo_fordagec), not the rates by order. Each age's rate
is split by the shares of the orders among that age's births of known order, and each
order's rates are summed as the total fertility rate is (``indicators._FERTILITY_AGES``).
So the orders add up to the total fertility rate, and births of unknown order are spread
as the known ones, as Eurostat's own shares of births by order are (VERIFIED for Greece,
1992-2024: these shares equal demo_find LBIRTHR1PC-LBIRTHR4_MAXPC to the decimal). The
mean age of each order computed from the same rates equals Eurostat's (demo_find
AGEMOTH1-AGEMOTH4_MAX) within its rounding and the rounding of the rates; the build checks
it. Greece only. Two tables in one value: provenance per ADR 0009.
"""

from __future__ import annotations

import polars as pl

from grpop.definitions import get_definition
from grpop.indicators import _FERTILITY_AGES, Data, Series
from grpop.provenance import Nature, Sex, Status, validate_observations
from grpop.sources.registry import get_source

GEO = "EL"
RATES = Series("eurostat_demo_frate", "fertility_rate@v1", Nature.OFFICIAL_ESTIMATE)
# Eurostat birth order -> (definition, demo_find code of its mean age at birth)
ORDERS = {
    "1": ("total_fertility_rate_order1@v1", "AGEMOTH1"),
    "2": ("total_fertility_rate_order2@v1", "AGEMOTH2"),
    "3": ("total_fertility_rate_order3@v1", "AGEMOTH3"),
    "GE4": ("total_fertility_rate_order4plus@v1", "AGEMOTH4_MAX"),
}
BIRTHS = {
    o: Series("eurostat_demo_fordagec", "live_births@v1", Nature.OFFICIAL_ESTIMATE, {"ord_brth": o})
    for o in ORDERS
}
MEAN_AGE = {
    o: Series(
        "eurostat_demo_find", "mean_age_childbearing@v1", Nature.OFFICIAL_ESTIMATE, {"indic_de": c}
    )
    for o, (_, c) in ORDERS.items()
}
SOURCES = frozenset({RATES.source_id, BIRTHS["1"].source_id, MEAN_AGE["1"].source_id})
TRANSFORM_VERSION = "total_fertility_rate_by_order@0.1"
# The middle of each age class in years: completed age plus a half
_MIDDLE = {"10-14": 12.5, "50+": 52.5, **{str(a): a + 0.5 for a in range(15, 50)}}
# AGEMOTH has one decimal; the rates have five, which moves our mean age by up to 0.01
MEAN_AGE_TOLERANCE = 0.05 + 0.01
_FLAGS = ["provisional", "break_in_series"]
_DATES = ["vintage", "retrieved_at"]


def _read(series: Series, data: Data) -> pl.DataFrame:
    df = series.read(data).filter(pl.col("geo_code") == GEO, pl.col("value").is_not_null())
    return df.with_columns(provisional=pl.col("status") == Status.PROVISIONAL.value)


def rates(data: Data) -> pl.DataFrame:
    """Age-specific fertility rates by order: period, age, order, value, provenance. Only
    the years where every age class has a rate and its births of known order."""
    births = pl.concat(
        _read(s, data).with_columns(order=pl.lit(o)) for o, s in BIRTHS.items()
    ).filter(pl.col("age").is_in(list(_FERTILITY_AGES)))
    known = births.group_by("period", "age").agg(known=pl.col("value").sum())
    rate = _read(RATES, data).filter(pl.col("age").is_in(list(_FERTILITY_AGES)))
    df = (
        births.join(known, on=["period", "age"])
        .join(rate, on=["period", "age"], suffix="_rate")
        .with_columns(
            value=pl.when(pl.col("known") > 0)
            .then(pl.col("value_rate") * pl.col("value") / pl.col("known"))
            .when(pl.col("value_rate") == 0)
            .then(0.0),  # null: a rate without births of known order
            **{c: pl.col(c) | pl.col(f"{c}_rate") for c in _FLAGS},
            **{c: pl.max_horizontal(c, f"{c}_rate") for c in _DATES},
        )
    )
    complete = (
        df.group_by("period")
        .agg(n=pl.col("value").is_not_null().sum())
        .filter(pl.col("n") == len(_FERTILITY_AGES) * len(ORDERS))
    )
    return df.join(complete.select("period"), on="period").select(
        "period", "age", "order", "value", "source_url", *_FLAGS, *_DATES
    )


def by_order(data: Data) -> pl.DataFrame:
    """Total fertility rate and mean age at birth of each order, per year."""
    width = pl.col("age").replace_strict(_FERTILITY_AGES, return_dtype=pl.Float64)
    middle = pl.col("age").replace_strict(_MIDDLE, return_dtype=pl.Float64)
    weighted = pl.col("value") * width
    return (
        rates(data)
        .sort("period", "order", "age")  # a float sum in a fixed order: same bytes each build
        .group_by("period", "order", maintain_order=True)
        .agg(
            tfr=weighted.sum(),
            mean_age=(weighted * middle).sum() / weighted.sum(),
            source_url=pl.col("source_url").first(),
            **{c: pl.col(c).any() for c in _FLAGS},
            **{c: pl.col(c).max() for c in _DATES},
        )
    )


def check_mean_ages(orders: pl.DataFrame, data: Data) -> None:
    """Raises where an order's mean age differs from Eurostat's by more than rounding."""
    official = pl.concat(
        _read(s, data).select("period", order=pl.lit(o), official="value")
        for o, s in MEAN_AGE.items()
    )
    off = orders.join(official, on=["period", "order"]).filter(
        (pl.col("mean_age") - pl.col("official")).abs() > MEAN_AGE_TOLERANCE
    )
    if off.height:
        with pl.Config(tbl_rows=-1):
            raise ValueError(f"mean age at birth by order differs from Eurostat:\n{off}")


def total_fertility_rate_by_order(data: Data) -> pl.DataFrame:
    """The four orders' total fertility rates as observations, checked against Eurostat."""
    orders = by_order(data)
    check_mean_ages(orders, data)
    definition = {o: get_definition(d) for o, (d, _) in ORDERS.items()}
    tables = [get_source(s.source_id) for s in (BIRTHS["1"], RATES)]  # ADR 0009
    return validate_observations(
        orders.select(
            metric=pl.col("order").replace_strict({o: d.metric for o, d in definition.items()}),
            definition_id=pl.col("order").replace_strict({o: d.id for o, d in definition.items()}),
            geo_code=pl.lit(GEO),
            geo_vintage=pl.lit("NUTS2024"),
            period="period",
            sex=pl.lit(Sex.TOTAL.value),
            age=pl.lit("total"),
            value="tfr",
            unit=pl.col("order").replace_strict({o: d.unit for o, d in definition.items()}),
            source=pl.lit(" + ".join(dict.fromkeys(t.provider for t in tables))),
            dataset_code=pl.lit("+".join(t.dataset_code for t in tables)),
            source_url="source_url",
            vintage="vintage",
            retrieved_at="retrieved_at",
            transform_version=pl.lit(TRANSFORM_VERSION),
            nature=pl.lit(Nature.DERIVED.value),
            status=pl.when("provisional")
            .then(pl.lit(Status.PROVISIONAL.value))
            .otherwise(pl.lit(Status.FINAL.value)),
            break_in_series="break_in_series",
            scenario_id=pl.lit(None, dtype=pl.String),
            interval=pl.lit(None, dtype=pl.String),
        ).sort("definition_id", "period")
    )
