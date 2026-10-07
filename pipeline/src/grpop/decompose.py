"""The change in live births, split into women and fertility (Δ9a).

Births of a year are the sum over the mother's age of women times the age-specific
fertility rate. Their change from the year before is split, age by age, into the part
from the number of women (the change in women times the mean rate of the two years)
and the part from fertility (the change in the rate times the mean number of women),
which add up exactly to the change. Women are the mean of the female population on
1 January of the year and of the next; the open classes 10-14 and 50+ take the women
aged 10-14 and 50-54, as Eurostat's own fertility rates do (VERIFIED: with these
denominators demo_frate's rates give demo_gind's births to the unit for Greece in
1998-2010 and 2024). Greece only.

The values combine two tables, so their provenance follows ADR 0009.
"""

from __future__ import annotations

import polars as pl

from grpop.definitions import get_definition
from grpop.indicators import Data, Series
from grpop.provenance import Nature, Sex, Status, validate_observations
from grpop.sources.registry import get_source

BIRTHS = Series(
    "eurostat_demo_fagec", "live_births@v1", Nature.OFFICIAL_ESTIMATE, select={"indic_de": "LBIRTH"}
)
WOMEN = Series("eurostat_demo_pjan", "population_1jan@v1", Nature.OFFICIAL_ESTIMATE)
SOURCES = frozenset({BIRTHS.source_id, WOMEN.source_id})
PARTS = {"women": "births_change_women@v1", "fertility": "births_change_fertility@v1"}
TRANSFORM_VERSION = "births_decomposition@0.1"
GEO = "EL"
# Mother's age class -> the single ages of the women it is divided by
CLASSES = {"10-14": range(10, 15), **{str(a): [a] for a in range(15, 50)}, "50+": range(50, 55)}
_CLASS_OF = {str(a): c for c, ages in CLASSES.items() for a in ages}
_WIDTH = {c: len(ages) for c, ages in CLASSES.items()}
_FLAGS = ["provisional", "break_in_series"]
_DATES = ["vintage", "retrieved_at"]


def _read(series: Series, data: Data) -> pl.DataFrame:
    df = series.read(data).filter(pl.col("geo_code") == GEO, pl.col("value").is_not_null())
    return df.with_columns(provisional=pl.col("status") == Status.PROVISIONAL.value)


def _births(data: Data) -> pl.DataFrame:
    """Births by mother's age class, in the years where every class is given and no birth
    is of unknown age (Greece: 1989 and from 1991), checked to add up
    to the year's total."""
    df = _read(BIRTHS, data)
    classes = df.filter(pl.col("age").is_in(list(CLASSES)))
    years = (
        classes.group_by("period")
        .agg(pl.col("value").sum(), n=pl.len())
        .join(df.filter(pl.col("age") == "total").select("period", total="value"), on="period")
        .join(
            df.filter(pl.col("age") == "unknown").select("period", unknown="value"),
            on="period",
            how="left",
        )
        .filter(pl.col("n") == len(CLASSES), pl.col("unknown").fill_null(0) == 0)
    )
    wrong = years.filter(pl.col("value") != pl.col("total"))
    if wrong.height:
        raise ValueError(f"births by age class do not add up to the total:\n{wrong}")
    return classes.join(years.select("period"), on="period").select(
        "period", "age", "value", "source_url", *_FLAGS, *_DATES
    )


def _women(data: Data) -> pl.DataFrame:
    """Mean female population of each year by age class: 1 January of it and the next."""
    jan = (
        _read(WOMEN, data)
        .filter(pl.col("sex") == Sex.FEMALE.value, pl.col("age").is_in(list(_CLASS_OF)))
        .group_by("period", age=pl.col("age").replace_strict(_CLASS_OF))
        .agg(pl.col("value").sum(), pl.col(*_FLAGS).any(), pl.col(*_DATES).max(), n=pl.len())
        .filter(pl.col("n") == pl.col("age").replace_strict(_WIDTH))
    )
    following = jan.with_columns(period=(pl.col("period").cast(pl.Int32) - 1).cast(pl.String))
    return jan.join(following, on=["period", "age"], suffix="_next").select(
        "period",
        "age",
        value=(pl.col("value") + pl.col("value_next")) / 2,
        **{c: pl.col(c) | pl.col(f"{c}_next") for c in _FLAGS},
        **{c: pl.max_horizontal(c, f"{c}_next") for c in _DATES},
    )


def _parts(data: Data) -> pl.DataFrame:
    """Both parts by year (the later of the two) and age class, checked to add up."""
    years = (
        _births(data)
        .join(_women(data), on=["period", "age"], suffix="_w")
        .with_columns(rate=pl.col("value") / pl.col("value_w"))
    )
    before = years.with_columns(period=(pl.col("period").cast(pl.Int32) + 1).cast(pl.String))
    both = years.join(before, on=["period", "age"], suffix="_b")
    every = {c: [c, f"{c}_w", f"{c}_b", f"{c}_w_b"] for c in [*_FLAGS, *_DATES]}
    parts = both.select(
        "period",
        "age",
        "source_url",
        women=(pl.col("value_w") - pl.col("value_w_b")) * (pl.col("rate") + pl.col("rate_b")) / 2,
        fertility=(pl.col("rate") - pl.col("rate_b"))
        * (pl.col("value_w") + pl.col("value_w_b"))
        / 2,
        change=pl.col("value") - pl.col("value_b"),
        **{c: pl.any_horizontal(every[c]) for c in _FLAGS},
        **{c: pl.max_horizontal(every[c]) for c in _DATES},
    )
    off = parts.filter((pl.col("women") + pl.col("fertility") - pl.col("change")).abs() > 1e-6)
    if off.height:
        raise ValueError(f"the parts do not add up to the change in births:\n{off}")
    totals = parts.group_by("period").agg(
        pl.lit("total").alias("age"),
        pl.col("source_url").first(),
        pl.col("women", "fertility", "change").sum(),
        pl.col(*_FLAGS).any(),
        pl.col(*_DATES).max(),
    )
    return pl.concat([parts, totals.select(parts.columns)])


def births_change(data: Data) -> pl.DataFrame:
    """Both parts of each year's change by age class and in total, as observations."""
    long = _parts(data).unpivot(
        list(PARTS), index=["period", "age", "source_url", *_FLAGS, *_DATES], variable_name="part"
    )
    definition = {part: get_definition(d) for part, d in PARTS.items()}
    tables = [get_source(s.source_id) for s in (BIRTHS, WOMEN)]  # numerator first (ADR 0009)
    return validate_observations(
        long.select(
            metric=pl.col("part").replace_strict({k: d.metric for k, d in definition.items()}),
            definition_id=pl.col("part").replace_strict(PARTS),
            geo_code=pl.lit(GEO),
            geo_vintage=pl.lit("NUTS2024"),
            period="period",
            sex=pl.lit(Sex.TOTAL.value),
            age="age",
            value="value",
            unit=pl.col("part").replace_strict({k: d.unit for k, d in definition.items()}),
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
        ).sort("definition_id", "period", "age")
    )
