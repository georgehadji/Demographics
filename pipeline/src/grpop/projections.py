"""Official projections: EUROPOP2025 (proj_25np, ADR 0008) and UN WPP 2024.

The baseline is ``projected``. Eurostat's sensitivity tests change one assumption of
the baseline each, so they are ``scenario`` rows with a ``scenario_id`` per test. A
projection type not listed here raises, so a new one is noticed. EUROPOP gives no
uncertainty intervals: ``interval`` stays null.
"""

from __future__ import annotations

import polars as pl

from grpop.indicators import Data, Series
from grpop.parse import eurostat
from grpop.provenance import AGE_TOTAL, Nature, Sex, validate_observations

SOURCE = "eurostat_proj_25np"
BASELINE = "BSL"
SCENARIOS = {
    "LFRT": "europop2025_lower_fertility",
    "LMRT": "europop2025_lower_mortality",
    "HMIGR": "europop2025_higher_migration",
    "LMIGR": "europop2025_lower_migration",
    "NMIGR": "europop2025_no_migration",
    "DCONV": "europop2025_delayed_convergence",
}
BASE_YEAR = "2025"
# Base-year totals that differ from demo_pjan (checked 2026-10-03, demo_pjan of that
# date): PL by 991,625 and SK by 131,528; EU27_2020 and EA21 by their sum.
# INFERENCE: demo_pjan was revised for PL and SK after EUROPOP2025 took its base
# population. The build fails if a difference appears or goes away.
KNOWN_BASE_DIFFERENCES = frozenset({"PL", "SK", "EU27_2020", "EA21"})


def read(data: Data) -> pl.DataFrame:
    """Baseline and sensitivity tests of every area, all ages and sexes."""
    codes = set(
        eurostat._parsed(data[SOURCE][1])[0]["dimension"]["projection"]["category"]["index"]
    )
    if codes != {BASELINE, *SCENARIOS}:
        raise ValueError(
            f"{SOURCE}: unknown projection types {sorted(codes - {BASELINE, *SCENARIOS})}"
        )

    def one(code: str) -> pl.DataFrame:
        series = Series(SOURCE, "population_1jan@v1", Nature.PROJECTED, {"projection": code})
        return series.read(data)

    return validate_observations(
        pl.concat(
            [
                one(BASELINE),
                *(
                    one(code).with_columns(
                        nature=pl.lit(Nature.SCENARIO.value), scenario_id=pl.lit(scenario)
                    )
                    for code, scenario in SCENARIOS.items()
                ),
            ]
        )
    )


def totals(projections: pl.DataFrame, observed: pl.DataFrame) -> pl.DataFrame:
    """Totals of every area, after checking the baseline's base year against the
    observed population (``KNOWN_BASE_DIFFERENCES``)."""
    total = (pl.col("sex") == Sex.TOTAL.value) & (pl.col("age") == AGE_TOTAL)
    base = projections.filter(
        total & (pl.col("nature") == Nature.PROJECTED.value) & (pl.col("period") == BASE_YEAR)
    ).select("geo_code", projected="value")
    obs = observed.filter(total & (pl.col("period") == BASE_YEAR)).select(
        "geo_code", observed="value"
    )
    compared = base.join(obs, on="geo_code")
    differ = set(compared.filter(pl.col("projected") != pl.col("observed"))["geo_code"])
    unexplained = differ - KNOWN_BASE_DIFFERENCES
    gone = (KNOWN_BASE_DIFFERENCES & set(compared["geo_code"])) - differ
    if unexplained or gone:
        raise ValueError(
            f"{SOURCE} {BASE_YEAR} against the observed population: unexplained differences "
            f"{sorted(unexplained)}, listed differences gone {sorted(gone)}"
        )
    return projections.filter(total)


# UN WPP 2024 against demo_pjan: the WPP population on 1 July of a year against the mean
# of demo_pjan on 1 January of that year and the next (checked 2026-10-03 for 2024).
# Every peer within 6% (Greece -3.1%, the widest PL +5.4% and MT -5.1%), except CY:
# WPP covers the whole island, Eurostat the area under government control (+39%).
# INFERENCE for the rest: other reference date and population concept, and the UN's
# own estimates of the base population and of migration. The build fails on a larger
# difference not listed here, and on a listed one that is gone.
WPP_TOLERANCE = 0.06
WPP_KNOWN_DIFFERENCES = frozenset({"CY"})


def wpp_checked(wpp: pl.DataFrame, observed: pl.DataFrame) -> pl.DataFrame:
    """``wpp`` after checking its medians against the observed population."""
    jan = observed.filter((pl.col("sex") == Sex.TOTAL.value) & (pl.col("age") == AGE_TOTAL))
    mid = (
        jan.select("geo_code", "period", a="value")
        .join(
            jan.select(
                "geo_code", period=(pl.col("period").cast(pl.Int32) - 1).cast(pl.String), b="value"
            ),
            on=["geo_code", "period"],
        )
        .select("geo_code", "period", observed=(pl.col("a") + pl.col("b")) / 2)
    )
    compared = (
        wpp.filter(pl.col("interval").is_null())
        .join(mid, on=["geo_code", "period"])
        .with_columns(off=(pl.col("value") / pl.col("observed") - 1).abs() > WPP_TOLERANCE)
        .group_by("geo_code")
        .agg(pl.col("off").any())
    )
    differ = set(compared.filter("off")["geo_code"])
    unexplained = differ - WPP_KNOWN_DIFFERENCES
    gone = (WPP_KNOWN_DIFFERENCES & set(compared["geo_code"])) - differ
    if unexplained or gone:
        raise ValueError(
            f"WPP 2024 against the observed population: more than {WPP_TOLERANCE:.0%} off "
            f"{sorted(unexplained)}, listed differences gone {sorted(gone)}"
        )
    return wpp
