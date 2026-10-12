"""Population momentum (Δ9), and first its gate: WPP 2024's Momentum variant for Greece
reproduced by ``cohort.step`` from the UN's own inputs, before the step computes a
momentum of ours (CLAUDE.md: every model reproduces a published result first).

The Momentum variant (WPP 2024 Methodology, Table II.4): from 2024, fertility at
replacement (net reproduction rate 1), mortality constant, no migration. The UN's
conventions, each VERIFIED 2026-10-12 on Greece:

- The base is the medium variant's population on 1 January 2024; the variant's 1 July
  values are the mean of two 1 January values.
- Mortality is held at the 2023 life table: Momentum's female life expectancy is
  84.3312 every year, the medium variant's of 2023 (its 2024 is 84.4562). The survival
  ratios Sx become the step's rates by ``2(1 - S)/(1 + S)``, at age 0 ``4(1 - S)/(1 + S)``,
  so the step survives exactly as the UN does.
- Fertility is the variant's own ASFR by completed age 15-49. Births by the age reached
  during the year take the mean of the rates at x and x - 1 (with x alone or x - 1
  alone, births are about 1,000 a year off; with the mean, about 10 until 2060). The file leaves
  out mothers under 15 and over 49 (PASFR adds up to 99.83%), so births are scaled by
  100/sum(PASFR); with that the variant's NRR is 1.0001-1.0006.
- Boys per 100 girls at birth: the medium variant's SRB of the base year (106.4).

The gate compares the female population (one sex, as momentum is defined): the mean of
our 1 January values against the variant's 1 July value, 2024-2100. VERIFIED: at most
0.073% apart (2,943 persons, in 2100); the female deaths add up to the UN's within
200 persons over the period, the gap is in births after 2060 (40 to 110 a year, cause
UNKNOWN). What the gate does not check: no age detail (the UN publishes the variant's
totals only), and survival is the UN's by construction, so it checks the bookkeeping
(ageing, the open age group, births by age reached, the boys' share, the 1 July
convention); the EUROPOP2025 gate in ``cohort`` checks the rates. ponytail: Greece,
women only; the male life table (200 MB) when the total is needed.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from grpop.cohort import OPEN, step
from grpop.indicators import Data
from grpop.parse.un_wpp_csv import MOMENTUM, greece

POPULATION = "un_wpp_2024_population_by_sex"
BASE = "un_wpp_2024_population_1jan_single_age"
LIFE_TABLE = "un_wpp_2024_life_table_female_1950_2023"
FERTILITY = "un_wpp_2024_fertility_by_age1"
INDICATORS = "un_wpp_2024_indicators_medium"
SOURCES = frozenset({POPULATION, BASE, LIFE_TABLE, FERTILITY, INDICATORS})
BASE_YEAR = 2024
MORTALITY_YEAR = 2023
TOLERANCE = 0.001  # relative, any year


def _by_age(df: pl.DataFrame, column: str) -> np.ndarray:
    out = np.zeros(OPEN + 1)
    for x, value in df.select(pl.col("AgeGrpStart").cast(pl.Int32), column).iter_rows():
        out[x] = float(value)
    return out


def inputs(data: Data) -> tuple[np.ndarray, np.ndarray, dict[int, np.ndarray], float]:
    """Base population, mortality and boys' share as ``cohort.step`` takes them (women
    only, men zero), and the fertility of each year by age reached."""
    base = greece(data[BASE][1], ["Time", "AgeGrpStart", "PopFemale"])
    life = greece(data[LIFE_TABLE][1], ["Time", "AgeGrpStart", "Sx"])
    fertility = greece(data[FERTILITY][1], ["Variant", "Time", "AgeGrpStart", "ASFR", "PASFR"])
    indicators = greece(data[INDICATORS][1], ["Time", "SRB"])
    population = np.zeros((2, OPEN + 1))
    population[1] = _by_age(base.filter(pl.col("Time") == str(BASE_YEAR)), "PopFemale")
    s = _by_age(life.filter(pl.col("Time") == str(MORTALITY_YEAR)), "Sx")
    mortality = np.zeros((2, OPEN + 1))
    mortality[1] = 2 * (1 - s) / (1 + s)
    mortality[1, 0] = 4 * (1 - s[0]) / (1 + s[0])
    rates = {}
    for (year,), year_df in (
        fertility.filter(pl.col("Variant") == MOMENTUM).partition_by("Time", as_dict=True).items()
    ):
        asfr = _by_age(year_df, "ASFR") / 1000
        share = year_df["PASFR"].cast(pl.Float64).sum() / 100
        rates[int(year)] = (asfr + np.r_[0, asfr[:-1]]) / 2 / share
    srb = float(indicators.filter(pl.col("Time") == str(BASE_YEAR))["SRB"].item())
    return population, mortality, rates, srb / (100 + srb)


def reproduce(data: Data) -> pl.DataFrame:
    """The Momentum variant's female population from 2024 by our step, against the UN's:
    year, ours, theirs (thousands, 1 July). Raises if any year is more than
    ``TOLERANCE`` apart."""
    population, mortality, fertility, boys = inputs(data)
    target = greece(data[POPULATION][1], ["Variant", "Time", "PopFemale"])
    theirs = dict(
        target.filter(pl.col("Variant") == MOMENTUM).select("Time", "PopFemale").iter_rows()
    )
    zero = np.zeros_like(mortality)
    rows = []
    for year in sorted(fertility):
        new, _ = step(population, mortality, zero, fertility[year], boys)
        rows.append((year, (population[1].sum() + new[1].sum()) / 2, float(theirs[str(year)])))
        population = new
    df = pl.DataFrame(rows, schema=["year", "ours", "theirs"], orient="row")
    off = df.filter(((pl.col("ours") - pl.col("theirs")) / pl.col("theirs")).abs() > TOLERANCE)
    if off.height or df.height != len(theirs):
        raise ValueError(f"WPP 2024 Momentum not reproduced within {TOLERANCE}: {off.head(5)}")
    return df
