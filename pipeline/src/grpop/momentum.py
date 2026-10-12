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
200 persons over the period, the gap is in births after 2060 (about 40 to 110 a year, cause
UNKNOWN). What the gate does not check: no age detail (the UN publishes the variant's
totals only), and survival is the UN's by construction, so it checks the bookkeeping
(ageing, the open age group, births by age reached, the boys' share, the 1 July
convention); the EUROPOP2025 gate in ``cohort`` checks the rates. ponytail: Greece,
women only; the male life table (200 MB) when the total is needed.

Then Greece's own, every year, from Eurostat (``momentum``): the year's fertility rates
(demo_frate, by age completed: metadata section 3.4 and its agedef COMPLET, so taken by
age reached as in the gate; the classes 10-14 and 50+ over their single ages, so
mothers of every age count), the share of boys (demo_fasec), both sexes' life tables
(demo_mlifetable; survival L(x)/L(x-1) and, from 95, T(95)/(T(95) + L(94))) and the
population on 1 January (demo_pjan). Momentum: ``cohort.step`` from that population with
the rates scaled to replacement in the step's own terms (``net_reproduction``), the
mortality constant and no migration, until stationary; the ratio of that population to
the first, by sex. VERIFIED on 2023-2024: the stationary population per birth is the
life table's T(0)/l(0) within 1e-6, and the step's net reproduction rate is Δ9f's to
1e-4. Intrinsic growth rate: the root of the discrete renewal equation the step
follows, so a run at the year's own rates grows by it in the end. The engine's gate is
the WPP one above (a step of its own), since Eurostat publishes neither value.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from grpop import decompose, reproduction
from grpop.cohort import OPEN, step
from grpop.definitions import get_definition
from grpop.indicators import Data
from grpop.parse import eurostat
from grpop.parse.un_wpp_csv import MOMENTUM, greece
from grpop.provenance import AGE_TOTAL, Nature, Status, validate_observations

POPULATION = "un_wpp_2024_population_by_sex"
BASE = "un_wpp_2024_population_1jan_single_age"
LIFE_TABLE = "un_wpp_2024_life_table_female_1950_2023"
FERTILITY = "un_wpp_2024_fertility_by_age1"
INDICATORS = "un_wpp_2024_indicators_medium"
SOURCES = frozenset({POPULATION, BASE, LIFE_TABLE, FERTILITY, INDICATORS})
BASE_YEAR = 2024
MORTALITY_YEAR = 2023
TOLERANCE = 0.001  # relative, any year


def rates_from_survival(s: np.ndarray) -> np.ndarray:
    """Survival ratios by age reached (``s[0]``: from birth to 1 January) as the rates
    ``cohort.step`` takes, which survive by (1 - m/2)/(1 + m/2), at age 0 (1 - m/4)/(1 + m/4)."""
    m = np.asarray(2 * (1 - s) / (1 + s))
    m[..., 0] = 4 * (1 - s[..., 0]) / (1 + s[..., 0])
    return m


def by_age_reached(rates: np.ndarray) -> np.ndarray:
    """Fertility rates by completed age x as rates by the age reached during the year:
    the mean of the rates at x and x - 1."""
    return np.asarray((rates + np.r_[0, rates[:-1]]) / 2)


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
    mortality[1] = rates_from_survival(s)
    rates = {}
    for (year,), year_df in (
        fertility.filter(pl.col("Variant") == MOMENTUM).partition_by("Time", as_dict=True).items()
    ):
        asfr = _by_age(year_df, "ASFR") / 1000
        share = year_df["PASFR"].cast(pl.Float64).sum() / 100
        rates[int(year)] = by_age_reached(asfr) / share
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


# Greece's momentum and intrinsic growth rate from Eurostat tables, every year
RATES, GIRLS, DYING, WOMEN = (
    reproduction.RATES,
    reproduction.GIRLS,
    reproduction.DYING,
    decompose.WOMEN,
)
EUROSTAT_SOURCES = frozenset(s.source_id for s in (RATES, GIRLS, DYING, WOMEN))
GEO = "EL"
MOMENTUM_ID = "population_momentum@v1"
INTRINSIC_ID = "intrinsic_growth_rate@v1"
TRANSFORM_VERSION = "momentum@0.1"
LAST = 95  # demo_mlifetable: single ages 0-94 and 95+
STEADY = 1e-10  # relative change of the total a year, held for a generation
GENERATION = 35
MAX_YEARS = 5000
_SEXES = {"M": 0, "F": 1}
# demo_frate's classes (age completed: metadata §3.4, agedef COMPLET) -> single ages
_CLASSES = {
    "Y10-14": range(10, 15),
    **{f"Y{a}": range(a, a + 1) for a in range(15, 50)},
    "Y_GE50": range(50, 55),
}


@dataclass(frozen=True)
class Year:
    """One year's inputs as ``cohort.step`` takes them. ``exposure`` is a woman's
    person-years at each age reached per girl born, (L(x - 1) + L(x)) / 2 l(0)."""

    population: np.ndarray
    mortality: np.ndarray
    fertility: np.ndarray
    boys: float
    exposure: np.ndarray


def _raw(data: Data, source_id: str) -> pl.DataFrame:
    df = eurostat._parsed(data[source_id][1])[1]
    return df.filter(pl.col("geo") == GEO, pl.col("value").is_not_null())


def _single(code: str) -> int:
    return {"Y_LT1": 0, "Y_OPEN": OPEN}[code] if code in ("Y_LT1", "Y_OPEN") else int(code[1:])


def _life(data: Data) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Survival ratios by sex and age reached and the female exposure, for every
    year with a complete table. Ages 95 and over survive by T(95) / (T(95) + L(94)), so
    that a cohort keeps T(95) per l(0) above 95, as the life table does."""
    df = _raw(data, DYING.source_id).filter(pl.col("sex").is_in(list(_SEXES)))
    out = {}
    for (year,), year_df in df.partition_by("time", as_dict=True).items():
        cells = {
            (i, a, s): v
            for i, a, s, v in year_df.select("indic_de", "age", "sex", "value").iter_rows()
        }
        ages = ["Y_LT1", *(f"Y{x}" for x in range(1, LAST))]
        try:
            lived = {s: np.array([cells["PYLIVED", a, s] for a in ages]) for s in _SEXES}
            top = {s: cells["TOTPYLIVED", f"Y_GE{LAST}", s] for s in _SEXES}
            born = {s: cells["SURVIVORS", "Y_LT1", s] for s in _SEXES}
        except KeyError:
            continue
        s = np.zeros((2, OPEN + 1))
        for sex, i in _SEXES.items():
            L = lived[sex]
            s[i, 0] = L[0] / born[sex]
            s[i, 1:LAST] = L[1:] / L[:-1]
            s[i, LAST:] = top[sex] / (top[sex] + L[-1])
        exposure = np.zeros(OPEN + 1)
        exposure[1:LAST] = (lived["F"][:-1] + lived["F"][1:]) / 2 / born["F"]
        out[int(year)] = (s, exposure)
    return out


def inputs_eurostat(data: Data) -> dict[int, Year]:
    """Every year in which all four tables are complete for Greece: the population on
    1 January, that year's life table, fertility rates and share of boys."""
    pop = _raw(data, WOMEN.source_id).filter(
        pl.col("sex").is_in(list(_SEXES)), pl.col("age").str.contains(r"^Y(_LT1|\d+|_OPEN)$")
    )
    rates = _raw(data, RATES.source_id).filter(pl.col("age").is_in(list(_CLASSES)))
    births = _raw(data, GIRLS.source_id).filter(pl.col("age") == "TOTAL")
    out = {}
    for year, (s, exposure) in sorted(_life(data).items()):
        p = pop.filter(pl.col("time") == str(year))
        r = rates.filter(pl.col("time") == str(year))
        b = dict(births.filter(pl.col("time") == str(year)).select("sex", "value").iter_rows())
        if p.height != 2 * (OPEN + 1) or r.height != len(_CLASSES) or not {"M", "T"} <= b.keys():
            continue
        population = np.zeros((2, OPEN + 1))
        for sex, age, value in p.select("sex", "age", "value").iter_rows():
            population[_SEXES[sex], _single(age)] = value
        completed = np.zeros(OPEN + 1)
        for age, value in r.select("age", "value").iter_rows():
            completed[list(_CLASSES[age])] = value
        fertility = by_age_reached(completed)
        boys = b["M"] / b["T"]
        out[year] = Year(population, rates_from_survival(s), fertility, boys, exposure)
    return out


def net_reproduction(y: Year) -> float:
    """Daughters per woman in the step's own terms: 1 is the rate it is stationary at."""
    return float((1 - y.boys) * y.fertility @ y.exposure)


def stationary(y: Year, fertility: np.ndarray) -> tuple[np.ndarray, float]:
    """The population on 1 January and the year's births once ``cohort.step``, with
    these rates held constant and no migration, changes the total by less than
    ``STEADY`` a year for a generation. Raises if it never does."""
    population, zero, steady = y.population, np.zeros_like(y.mortality), 0
    for _ in range(MAX_YEARS):
        new, births = step(population, y.mortality, zero, fertility, y.boys)
        steady = steady + 1 if abs(new.sum() / population.sum() - 1) < STEADY else 0
        population = new
        if steady > GENERATION:
            return population, births
    raise ValueError(f"not stationary after {MAX_YEARS} years")


def intrinsic_growth(y: Year) -> float:
    """The factor lambda with (1 - boys) sum f(x) lambda^-x exposure(x) = 1, the discrete
    Euler-Lotka equation as the step renews births; ln(lambda) is the intrinsic rate."""
    ages = np.arange(OPEN + 1, dtype=float)

    def excess(growth: float) -> float:
        return float((1 - y.boys) * (y.fertility * growth**-ages) @ y.exposure) - 1

    low, high = 0.5, 2.0
    for _ in range(100):
        mid = (low + high) / 2
        low, high = (mid, high) if excess(mid) > 0 else (low, mid)
    return (low + high) / 2


def _values(data: Data) -> pl.DataFrame:
    rows = []
    for year, y in inputs_eurostat(data).items():
        ultimate, _ = stationary(y, y.fertility / net_reproduction(y))
        for sex, i in (("total", slice(None)), ("male", 0), ("female", 1)):
            ratio = float(ultimate[i].sum() / y.population[i].sum())
            rows.append((str(year), MOMENTUM_ID, sex, ratio))
        rows.append((str(year), INTRINSIC_ID, "total", 100 * float(np.log(intrinsic_growth(y)))))
    return pl.DataFrame(rows, schema=["period", "definition_id", "sex", "value"], orient="row")


def _provenance(data: Data) -> pl.DataFrame:
    """Per period, the four tables' provenance combined (ADR 0009), the rates' URL."""
    first, *others = (
        reproduction._year(reproduction._read(s, data), pl.col("value").first()).drop("value")
        for s in (RATES, GIRLS, DYING, WOMEN)
    )
    return reproduction._combine(first, *others)


def momentum(data: Data) -> pl.DataFrame:
    """Population momentum by sex and the intrinsic growth rate of Greece, every year."""
    definition = {d: get_definition(d) for d in (MOMENTUM_ID, INTRINSIC_ID)}
    rows = _values(data).join(_provenance(data), on="period")
    return validate_observations(
        rows.select(
            metric=pl.col("definition_id").replace_strict(
                {k: d.metric for k, d in definition.items()}
            ),
            definition_id="definition_id",
            geo_code=pl.lit(GEO),
            geo_vintage=pl.lit("NUTS2024"),
            period="period",
            sex="sex",
            age=pl.lit(AGE_TOTAL),
            value="value",
            unit=pl.col("definition_id").replace_strict({k: d.unit for k, d in definition.items()}),
            **reproduction._tables(*(s.source_id for s in (RATES, GIRLS, DYING, WOMEN))),
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
        ).sort("definition_id", "period", "sex")
    )
