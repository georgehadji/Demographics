"""Net migration by age as the residual of each cohort (Δ9l), Greece.

The people who reach age a during year t (born in t - a) number P(a-1, t) on 1 January
of t and P(a, t+1) on 1 January of t+1 (demo_pjan); in between D(a, t) of them die
(demo_mager, deaths by age reached). Their net migration is the rest:

    M(a, t) = P(a, t+1) - P(a-1, t) + D(a, t)

with the year's live births of the sex (demo_fasec) in place of P(-1, t), and for the
open class k+ the population k-1 and k+ of 1 January of t. The ages add up to the
population change minus the natural change, Eurostat's net migration (demo_gind
CNMIGRAT): the build checks it to the person. By sex; years with an age missing, with
deaths or population of unknown age, or whose open class changes, are left out.

Against ELSTAT's flows by age (migr_imm8 minus migr_emi2, age in completed years), Greece
2022-2024: within 41 persons at every age below 50 and within 104 below 70 (VERIFIED
2026-10-10; the test checks 2023-2024), from 70 up to 900 apart (at 81, the cohorts of
1941-1943), while both add up to the same total in 2023 and 2024. INFERENCE: the
population estimates are adjusted at old ages, and the residual absorbs the adjustment.
"""

from __future__ import annotations

import polars as pl

from grpop import reproduction
from grpop.definitions import get_definition
from grpop.indicators import SERIES, Data, Series
from grpop.provenance import AGE_TOTAL, Nature, Status, validate_observations
from grpop.sources.registry import get_source

GEO = "EL"
POPULATION = SERIES["population"]
DEATHS = Series("eurostat_demo_mager", "deaths_by_age_reached@v1", Nature.OBSERVED)
BIRTHS = reproduction.GIRLS
NET_MIGRATION = SERIES["net_migration"]
SOURCES = frozenset(s.source_id for s in (POPULATION, DEATHS, BIRTHS, NET_MIGRATION))
DEFINITION = "net_migration_by_age@v1"
TRANSFORM_VERSION = "cohort_residual@0.1"
_FLAGS = ["provisional", "break_in_series"]
_DATES = ["vintage", "retrieved_at"]
_KEY = ["sex", "period", "x"]


def _read(series: Series, data: Data) -> pl.DataFrame:
    """Single ages and the open class as x, with its lower bound k; a sex and period
    with any of unknown age is left out."""
    df = reproduction._read(series, data)
    unknown = df.filter(pl.col("age") == "unknown", pl.col("value") != 0).select("sex", "period")
    return (
        df.join(unknown, on=["sex", "period"], how="anti")
        .filter(pl.col("age").str.contains(r"^\d+\+?$"))
        .with_columns(
            x=pl.col("age").str.strip_suffix("+").cast(pl.Int32),
            open=pl.col("age").str.ends_with("+"),
        )
        .with_columns(k=pl.col("x").filter(pl.col("open")).first().over("sex", "period"))
        .filter(pl.col("k").is_not_null())
        .select(*_KEY, "k", "value", *_FLAGS, *_DATES)
    )


def _next_year(period: pl.Expr, years: int) -> pl.Expr:
    return (period.cast(pl.Int32) + years).cast(pl.String)


def _parts(data: Data) -> pl.DataFrame:
    """after, before and deaths of each cohort, by sex, period and age reached."""
    pop = _read(POPULATION, data)
    after = pop.with_columns(period=_next_year(pl.col("period"), -1))
    # population of the year before at a-1, the open class taking k-1 and k+
    before = (
        pop.with_columns(x=pl.min_horizontal(pl.col("x") + 1, "k"))
        .group_by("sex", "period", "x")
        .agg(
            pl.col("k").first(),
            pl.col("value").sum(),
            *(pl.col(c).any() for c in _FLAGS),
            *(pl.col(c).max() for c in _DATES),
        )
    )
    births = (
        reproduction._read(BIRTHS, data)
        .filter(pl.col("age") == AGE_TOTAL)
        .with_columns(x=pl.lit(0, pl.Int32))
        .select(*_KEY, "value", *_FLAGS, *_DATES)
    )
    before = pl.concat([before, births], how="diagonal").with_columns(
        k=pl.col("k").max().over("sex", "period")
    )
    deaths = _read(DEATHS, data)
    parts = after.join(before, on=_KEY, suffix="_before").join(deaths, on=_KEY, suffix="_deaths")
    return parts.filter(pl.col("k") == pl.col("k_before"), pl.col("k") == pl.col("k_deaths"))


def residual(data: Data) -> pl.DataFrame:
    """Net migration by single age reached (the open class at its bound): sex, period,
    x, open, value and the combined flags and dates."""
    parts = _parts(data)
    complete = (
        parts.group_by("sex", "period")
        .agg(n=pl.len(), k=pl.col("k").first())
        .filter(pl.col("n") == pl.col("k") + 1)
        .select("sex", "period")
    )
    three = ["", "_before", "_deaths"]
    return (
        parts.join(complete, on=["sex", "period"])
        .select(
            *_KEY,
            open=pl.col("x") == pl.col("k"),
            value=pl.col("value") - pl.col("value_before") + pl.col("value_deaths"),
            **{c: pl.any_horizontal(f"{c}{s}" for s in three) for c in _FLAGS},
            **{c: pl.max_horizontal(f"{c}{s}" for s in three) for c in _DATES},
        )
        .sort(_KEY)
    )


def check_total(data: Data, totals: pl.DataFrame) -> None:
    """The ages of both sexes add up to demo_gind CNMIGRAT, to the person."""
    official = reproduction._read(NET_MIGRATION, data).select("sex", "period", official="value")
    off = totals.join(official, on=["sex", "period"]).filter(pl.col("value") != pl.col("official"))
    if not off.is_empty():
        raise ValueError(f"{DEFINITION}: ages do not add up to CNMIGRAT: {off.head(5).rows()}")


def net_migration_by_age(data: Data) -> pl.DataFrame:
    """Net migration by age reached and its total, by sex, as observations."""
    single = residual(data).with_columns(
        age=pl.when("open")
        .then(pl.col("x").cast(pl.String) + "+")
        .otherwise(pl.col("x").cast(pl.String))
    )
    total = single.group_by("sex", "period", maintain_order=True).agg(
        pl.col("value").sum(),
        *(pl.col(c).any() for c in _FLAGS),
        *(pl.col(c).max() for c in _DATES),
    )
    check_total(data, total)
    rows = pl.concat([single, total.with_columns(age=pl.lit(AGE_TOTAL))], how="diagonal")
    tables = [get_source(s.source_id) for s in (POPULATION, DEATHS, BIRTHS)]
    first = reproduction._read(POPULATION, data)["source_url"].first()
    definition = get_definition(DEFINITION)
    return validate_observations(
        rows.select(
            metric=pl.lit(definition.metric),
            definition_id=pl.lit(DEFINITION),
            geo_code=pl.lit(GEO),
            geo_vintage=pl.lit("NUTS2024"),
            period="period",
            sex="sex",
            age="age",
            value="value",
            unit=pl.lit(definition.unit),
            source=pl.lit(" + ".join(dict.fromkeys(t.provider for t in tables))),
            dataset_code=pl.lit("+".join(t.dataset_code for t in tables)),
            source_url=pl.lit(first, dtype=pl.String),
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
        ).sort("period", "sex", "age")
    )
