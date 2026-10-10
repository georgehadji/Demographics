"""Net migration by age as the residual of each cohort (Δ9l), Greece.

The people who reach age a during year t (born in t - a) number P(a-1, t) on 1 January
of t and P(a, t+1) on 1 January of t+1 (demo_pjan); in between D(a, t) of them die
(demo_mager, deaths by age reached). Their net migration is the rest:

    M(a, t) = P(a, t+1) - P(a-1, t) + D(a, t)

with the year's live births of the sex (demo_fasec) in place of P(-1, t), and for the
open class k+ the population k-1 and k+ of 1 January of t. The ages add up to the
population change minus the natural change, Eurostat's net migration (demo_gind
CNMIGRAT): the build checks it to the person, except the years of ``KNOWN_DIFFERENCES``.
By sex; years with an age missing, with deaths or population of unknown age, or whose
open class changes, are left out. Greece: 2007-2024, as births by sex (demo_fasec) start
in 2007; population and deaths by age go back to 1985 (VERIFIED 2026-10-10). ponytail:
the years before 2007 for both sexes need the total births of demo_gind; add them if a
page needs a longer series.

Against ELSTAT's flows by age (migr_imm8 minus migr_emi2, age in completed years), Greece
2022-2024: within 41 persons at every age below 50 and within 104 below 70 (VERIFIED
2026-10-10; the test checks 2023-2024), from 70 up to 900 apart (at 81, the cohorts of
1941-1943), while both add up to the same total in 2023 and 2024. INFERENCE: the
population estimates are adjusted at old ages, and the residual absorbs the adjustment.
UNKNOWN whether ELSTAT's age in completed years is the age at the move or at the end of
the year; the residual by age reached matches the flows at the same age, and not half a
year apart, which points to the latter.
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
# Years whose total differs from CNMIGRAT. demo_gind (updated 2026-09-30) gives Greece on
# 1 January 2012 and 2013 11,086,406 and 11,003,615; demo_pjan 11,072,725 and 10,980,006.
# CNMIGRAT 2011 and 2012 are demo_gind's own population change minus natural change
# (-32,315 and -66,494); ours, from demo_pjan, -45,996 and -76,422. VERIFIED 2026-10-10.
# INFERENCE: the two tables were revised at different times; cause UNKNOWN.
# The check fails if a listed difference goes away.
KNOWN_DIFFERENCES = frozenset({"2011", "2012"})


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
    """The ages add up to demo_gind CNMIGRAT, to the person. CNMIGRAT has no sex: only
    the total of both sexes is checked. Years in ``KNOWN_DIFFERENCES`` must differ."""
    official = reproduction._read(NET_MIGRATION, data).select("sex", "period", official="value")
    compared = totals.join(official, on=["sex", "period"]).with_columns(
        known=pl.col("period").is_in(list(KNOWN_DIFFERENCES))
    )
    off = compared.filter(pl.col("value") != pl.col("official"), ~pl.col("known"))
    if not off.is_empty():
        raise ValueError(f"{DEFINITION}: ages do not add up to CNMIGRAT: {off.head(5).rows()}")
    gone = compared.filter(pl.col("value") == pl.col("official"), pl.col("known"))
    if not gone.is_empty():
        raise ValueError(f"{DEFINITION}: listed difference gone: {gone['period'].to_list()}")


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
