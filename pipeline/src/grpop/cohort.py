"""Cohort-component projection (PROPOSAL §5.2, level B) and its gate: EUROPOP2025's
baseline for Greece reproduced from EUROPOP2025's own assumptions.

The step follows EUROPOP2025's conventions, whose formulas are in PROPOSAL §5.2: rates
of mortality (proj_25naasmr) and fertility (proj_25naasfr) and net migration
(proj_25nanmig) by the age reached during the year, the year's births at half the
exposure. VERIFIED 2026-10-10: with them the step gives Eurostat's population of the
next year to rounding; read as rates by age in completed years, the deaths fall short of
proj_25ndbi's.

Eurostat does not publish its share of boys among births. The one that turns the
first projected year's births into its population aged 0 is 0.5130 (sex ratio 1.0534)
for Greece, Germany, Cyprus, Italy and Sweden alike (VERIFIED 2026-10-10; INFERENCE:
one assumption for every country); the gate takes it from that year, so it holds
without being typed. The gate starts from 2026: the population of 2026 does not follow
from 2025's assumptions (each sex 3,400 apart; INFERENCE: Eurostat aligns 2025 and
2026 with its nowcast, as the metadata says of the rates). Greece, 2026-2100: every age
and sex within ``TOLERANCE`` (the largest, 6.5 persons; the total within 51 in 2100),
the published inputs being rounded. ponytail: Greece only and the baseline only; other
countries and the sensitivity tests when a scenario needs them.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from grpop.indicators import Data
from grpop.parse import eurostat

GEO = "EL"
PROJECTION = "BSL"
POPULATION = "eurostat_proj_25np"
FERTILITY = "eurostat_proj_25naasfr"
MORTALITY = "eurostat_proj_25naasmr"
MIGRATION = "eurostat_proj_25nanmig"
SOURCES = frozenset({POPULATION, FERTILITY, MORTALITY, MIGRATION})
FIRST_YEAR = 2026
OPEN = 100  # ages 0..99 and 100+
SEXES = ("M", "F")
TOLERANCE = 10  # persons, any age, sex and year


def step(
    population: np.ndarray,
    mortality: np.ndarray,
    migration: np.ndarray,
    fertility: np.ndarray,
    boys: float,
) -> tuple[np.ndarray, float]:
    """Population on 1 January of the next year and the year's births.

    ``population``, ``mortality`` and ``migration`` are (2, OPEN + 1), males first, by
    age on 1 January and by age reached; ``fertility`` is (OPEN + 1,) by age reached.
    """
    m, g = mortality, migration
    reaching = np.column_stack([population[:, : OPEN - 1], population[:, OPEN - 1 :].sum(1)])
    new = np.empty_like(population)
    new[:, 1:] = (reaching * (1 - m[:, 1:] / 2) + g[:, 1:]) / (1 + m[:, 1:] / 2)
    women = (population[1, :-1] + new[1, 1:]) / 2  # reaching 1..100
    births = float(fertility[1:] @ women)
    by_sex = births * np.array([boys, 1 - boys])
    new[:, 0] = (by_sex * (1 - m[:, 0] / 4) + g[:, 0]) / (1 + m[:, 0] / 4)
    return new, births


def _age(code: pl.Expr, source_id: str) -> pl.Expr:
    """Single ages, Y_LT1 as 0 and the open class; fertility's classes under 15 and 50+
    at 14 and 50. Other groups (Y_LT15, Y_GE65 of proj_25np) are left out (null)."""
    classes = {"Y_LT15": 14, "Y_GE50": 50} if source_id == FERTILITY else {f"Y_GE{OPEN}": OPEN}
    single = code.str.extract(r"^Y(\d+)$").cast(pl.Int32)
    return code.replace_strict({"Y_LT1": 0, **classes}, default=single, return_dtype=pl.Int32)


def _table(data: Data, source_id: str) -> dict[int, np.ndarray]:
    """Greece's baseline by year: (2, OPEN + 1) by sex and single age; a table without
    sex (fertility) fills the female row."""
    df = eurostat._parsed(data[source_id][1])[1]
    df = df.filter(pl.col("geo") == GEO, pl.col("projection") == PROJECTION)
    df = df.with_columns(x=_age(pl.col("age"), source_id)).filter(pl.col("x").is_not_null())
    if "sex" not in df.columns:
        df = df.with_columns(sex=pl.lit("F"))
    out = {}
    for (year,), year_df in df.partition_by("time", as_dict=True).items():
        cells = np.zeros((2, OPEN + 1))
        for sex, x, value in year_df.select("sex", "x", "value").iter_rows():
            if sex in SEXES:
                cells[SEXES.index(sex), x] = value
        out[int(year)] = cells
    return out


def inputs(data: Data) -> tuple[dict[int, np.ndarray], ...]:
    population, mortality, migration, fertility = (
        _table(data, s) for s in (POPULATION, MORTALITY, MIGRATION, FERTILITY)
    )
    return population, mortality, migration, {t: f[1] for t, f in fertility.items()}


def boys_share(data: Data) -> float:
    """Share of boys among births, from the first projected year: the births of each sex
    that give its population aged 0 on the next 1 January."""
    population, mortality, migration, _ = inputs(data)
    m, g = mortality[FIRST_YEAR][:, 0], migration[FIRST_YEAR][:, 0]
    born = (population[FIRST_YEAR + 1][:, 0] * (1 + m / 4) - g) / (1 - m / 4)
    return float(born[0] / born.sum())


def reproduce(data: Data) -> pl.DataFrame:
    """Greece's baseline from 2026 by our step, against Eurostat's: year, sex, age, ours,
    theirs. Raises if any cell is more than ``TOLERANCE`` apart."""
    population, mortality, migration, fertility = inputs(data)
    boys = boys_share(data)
    ours = population[FIRST_YEAR]
    rows = []
    for t in range(FIRST_YEAR, max(population)):
        ours, _ = step(ours, mortality[t], migration[t], fertility[t], boys)
        theirs = population[t + 1]
        for i, sex in enumerate(SEXES):
            rows += [(t + 1, sex, x, ours[i, x], theirs[i, x]) for x in range(OPEN + 1)]
    df = pl.DataFrame(rows, schema=["year", "sex", "age", "ours", "theirs"], orient="row")
    off = df.filter((pl.col("ours") - pl.col("theirs")).abs() > TOLERANCE)
    if off.height:
        raise ValueError(f"EUROPOP2025 baseline not reproduced within {TOLERANCE}: {off.head(5)}")
    return df
