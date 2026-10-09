"""Indicators: specification, computation and agreement with the official value (ADR 0005, L4).

Each indicator is one ``Indicator`` entry in ``INDICATORS``: its definition (meaning
and unit, in definitions.yaml), its input series, a Polars formula and, where an
official source publishes the same indicator, that series. Acceptance tests are
generated from ``INDICATORS`` (tests/test_indicators.py): every indicator with an
official counterpart must agree with it within the official rounding. ``grpop-build``
runs the same comparison (``check``) on every country and year in a snapshot store.
``SERIES`` lists the official series published as the source gives them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import polars as pl

from grpop import harmonize
from grpop.definitions import get_definition
from grpop.parse import eurostat
from grpop.provenance import Nature, Status, validate_observations
from grpop.snapshots import Snapshot

# Snapshot and bytes per registry source id, as the build reads them from the store.
Data = Mapping[str, tuple[Snapshot, bytes]]
KEY = ["geo_code", "period", "sex", "age"]
# Input observations by name -> KEY + value + provisional + break_in_series + _CARRIED.
Formula = Callable[[dict[str, pl.DataFrame]], pl.DataFrame]
_CARRIED = ["source", "dataset_code", "source_url", "vintage", "retrieved_at", "geo_vintage"]


@dataclass(frozen=True)
class Series:
    """One metric of one source, as ``parse.eurostat.to_observations`` reads it."""

    source_id: str
    definition_id: str
    nature: Nature
    select: dict[str, str] = field(default_factory=dict)
    geo_vintage: str = "NUTS2024"
    # Breakdowns the source puts in the code instead of a dimension, e.g. {"sex": "male"}
    # for demo_pjanind MMEDAGEPOP or {"age": "0-14"} for PC_Y0_14.
    fixed: dict[str, str] = field(default_factory=dict)
    geo_prefix: str = ""  # keep only geo codes that start with it, e.g. "EL"
    # The decimals the source publishes, where the site's default formatting would lose
    # them (e.g. death rates of 0.00025).
    decimals: int | None = None

    def read(self, data: Data) -> pl.DataFrame:
        snapshot, raw = data[self.source_id]
        obs = eurostat.to_observations(
            snapshot,
            raw,
            definition_id=self.definition_id,
            nature=self.nature,
            geo_vintage=self.geo_vintage,
            select=self.select or None,
            geo_prefix=self.geo_prefix,
        )
        obs = harmonize.recode_nuts2010(obs)
        harmonize.check_greek_codes(obs)
        return obs.with_columns(**{k: pl.lit(v) for k, v in self.fixed.items()})


@dataclass(frozen=True)
class Indicator:
    definition_id: str  # meaning and unit
    transform_version: str  # changes whenever the formula changes
    inputs: dict[str, Series]
    formula: Formula
    official: tuple[Series, ...] = ()  # the same indicator as an official source publishes it
    decimals: int = 1  # rounding of the official value
    # Rounding error our value inherits from rounded inputs, added to the comparison
    # tolerance (e.g. a sum of 37 rates published to 5 decimals: 37 * 0.000005).
    input_rounding: float = 0.0
    # (geo_code, period) where the official value is known to differ from ours. Each set
    # is explained, with its evidence, where it is defined.
    known_differences: frozenset[tuple[str, str]] = frozenset()
    # The same indicator computed from another table of the official source. Where ours
    # differs from the official value but equals a corroborating value, the official
    # source disagrees with itself: the difference is explained without a list.
    corroboration: tuple[Indicator, ...] = ()


def carried() -> list[pl.Expr]:
    """Aggregations a formula adds to its group_by: status and provenance of the inputs.

    ponytail: provenance is copied from the first input row, so ``compute`` requires
    all inputs to come from one source. Inputs from several datasets need a
    provenance rule of their own.
    """
    return [
        (pl.col("status") == Status.PROVISIONAL.value).any().alias("provisional"),
        pl.col("break_in_series").any(),
        *(pl.col(c).first() for c in _CARRIED),
    ]


_GROUP = ["geo_code", "period", "sex"]


def _age_groups(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Persons of known age and in broad age groups, per geo_code, period and sex.

    65+ and 80+ are persons of known age minus the single ages below them, so the
    open-ended age class is not needed. A group is null where a single age it needs
    is missing.
    """
    age = pl.col("age").cast(pl.Int32, strict=False)  # null for total, unknown, bands, N+
    value = pl.col("value")

    def under(n: int) -> pl.Expr:
        return pl.when(value.filter(age < n).len() == n).then(value.filter(age < n).sum())

    return (
        inputs["population"]
        .filter(value.is_not_null())
        .group_by(_GROUP)
        .agg(
            *carried(),
            known=value.filter(pl.col("age") == "total").first()
            - value.filter(pl.col("age") == "unknown").sum(),
            under15=under(15),
            under65=under(65),
            under80=under(80),
        )
        .with_columns(
            y0_14=pl.col("under15"),
            y15_64=pl.col("under65") - pl.col("under15"),
            y65_=pl.col("known") - pl.col("under65"),
            y80_=pl.col("known") - pl.col("under80"),
        )
    )


def _broad_groups(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """As ``_age_groups``, from a table of broad age groups (0-14, 15-64, 65+); no 80+."""
    value, age = pl.col("value"), pl.col("age")
    return (
        inputs["population"]
        .filter(value.is_not_null())
        .group_by(_GROUP)
        .agg(
            *carried(),
            known=value.filter(age == "total").first() - value.filter(age == "unknown").sum(),
            y0_14=value.filter(age == "0-14").first(),
            y15_64=value.filter(age == "15-64").first(),
            y65_=value.filter(age == "65+").first(),
        )
        .with_columns(y80_=pl.lit(None, dtype=pl.Float64))
    )


def _per_100(numerator: pl.Expr, denominator: pl.Expr, groups: Formula = _age_groups) -> Formula:
    def formula(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
        return (
            groups(inputs)
            .with_columns(age=pl.lit("total"), value=numerator / denominator * 100)
            .filter(pl.col("value").is_not_null())
        )

    return formula


_SHARES = {"0-14": "y0_14", "15-64": "y15_64", "65+": "y65_", "80+": "y80_"}


def _shares(groups: Formula) -> Formula:
    def formula(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
        return pl.concat(
            groups(inputs).with_columns(
                age=pl.lit(band), value=pl.col(group) / pl.col("known") * 100
            )
            for band, group in _SHARES.items()
        ).filter(pl.col("value").is_not_null())

    return formula


def _median_age(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Interpolated linearly within the single year of age that holds the middle person
    of known age; only where every single age from 0 to that age is present."""
    pop = inputs["population"].filter(pl.col("value").is_not_null())
    value = pl.col("value")
    half = pop.group_by(_GROUP).agg(
        *carried(),
        half=(
            value.filter(pl.col("age") == "total").first()
            - value.filter(pl.col("age") == "unknown").sum()
        )
        / 2,
    )
    single = (
        pop.select(*_GROUP, "value", a=pl.col("age").cast(pl.Int32, strict=False))
        .drop_nulls("a")
        .sort(*_GROUP, "a")
        .with_columns(
            below=value.cum_sum().over(_GROUP) - value,
            # Ages are distinct and sorted, so a == its row index iff ages 0..a all exist.
            complete=pl.col("a") == pl.int_range(pl.len()).over(_GROUP),
        )
    )
    return (
        single.join(half, on=_GROUP)
        .filter(
            (pl.col("below") < pl.col("half"))
            & (pl.col("below") + value >= pl.col("half"))
            & pl.col("complete")
        )
        .with_columns(
            age=pl.lit("total"), value=pl.col("a") + (pl.col("half") - pl.col("below")) / value
        )
    )


def _tagged(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """All inputs in one frame, with the input name in column ``input``."""
    return pl.concat(df.with_columns(input=pl.lit(name)) for name, df in inputs.items()).filter(
        pl.col("value").is_not_null()
    )


def _growth_rate(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    value, name = pl.col("value"), pl.col("input")
    return (
        _tagged(inputs)
        .group_by(KEY)
        .agg(
            *carried(),
            value=value.filter(name == "change").first()
            / value.filter(name == "average").first()
            * 1000,
        )
        .filter(pl.col("value").is_not_null())
    )


EXCESS_BASELINE = range(2016, 2020)


def _excess_mortality(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Deaths of each month from the weekly deaths, each ISO week spread evenly over its
    seven days; only months whose every day is covered. Then the percentage above the
    mean of the same month in EXCESS_BASELINE, from the first month after it."""
    weeks = (
        inputs["deaths"]
        .filter((pl.col("sex") == "total") & pl.col("value").is_not_null())
        .with_columns(monday=(pl.col("period") + "-1").str.to_date("%G-W%V-%u"))
    )
    days = (
        weeks.with_columns(day=pl.date_ranges("monday", pl.col("monday") + pl.duration(days=6)))
        .explode("day", empty_as_null=True)
        .with_columns(period=pl.col("day").dt.strftime("%Y-%m"), value=pl.col("value") / 7)
        .sort("geo_code", "day")  # a float sum in a fixed order: same bytes each build
    )
    months = (
        days.group_by("geo_code", "period", "sex", "age", maintain_order=True)
        .agg(
            *carried(),
            value=pl.col("value").sum(),
            covered=pl.col("day").n_unique(),
            length=pl.col("day").first().dt.month_end().dt.day(),
        )
        .filter(pl.col("covered") == pl.col("length"))
        .with_columns(
            year=pl.col("period").str.head(4).cast(pl.Int32), month=pl.col("period").str.tail(2)
        )
    )
    baseline = (
        months.filter(pl.col("year").is_in(list(EXCESS_BASELINE)))
        .group_by("geo_code", "month", maintain_order=True)
        .agg(baseline=pl.col("value").mean(), n=pl.len())
        .filter(pl.col("n") == len(EXCESS_BASELINE))
    )
    return (
        months.filter(pl.col("year") > EXCESS_BASELINE[-1])
        .join(baseline, on=["geo_code", "month"])
        .with_columns(value=100 * (pl.col("value") - pl.col("baseline")) / pl.col("baseline"))
    )


def _sex_ratio(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Males per 100 females, all ages, per geo_code and period."""
    value, sex = pl.col("value"), pl.col("sex")
    return (
        inputs["population"]
        .filter((pl.col("age") == "total") & value.is_not_null())
        .group_by("geo_code", "period")
        .agg(
            *carried(),
            value=value.filter(sex == "male").first() / value.filter(sex == "female").first() * 100,
        )
        .filter(value.is_not_null())
        .with_columns(sex=pl.lit("total"), age=pl.lit("total"))
    )


# Age classes of demo_frate that make up the total fertility rate, with their width.
_FERTILITY_AGES = {"10-14": 5, **{str(a): 1 for a in range(15, 50)}, "50+": 5}


def _total_fertility(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Sum of rate times width over the classes in _FERTILITY_AGES: single ages 15-49 and
    the five-year open classes 10-14 and 50+, as demo_frate's own TOTAL is built. Only
    where every class has a rate."""
    rates = inputs["rates"].filter(
        pl.col("value").is_not_null() & pl.col("age").is_in(list(_FERTILITY_AGES))
    )
    width = pl.col("age").replace_strict(_FERTILITY_AGES, return_dtype=pl.Float64)
    return (
        rates.group_by(_GROUP)
        .agg(*carried(), n=pl.len(), value=(pl.col("value") * width).sum())
        .filter(pl.col("n") == len(_FERTILITY_AGES))
        .with_columns(age=pl.lit("total"))
    )


def _cells(spec: str) -> frozenset[tuple[str, str]]:
    """'LT 2015-2020, HR 2013' -> {("LT", "2015"), ..., ("LT", "2020"), ("HR", "2013")}."""
    cells = set()
    for item in spec.split(","):
        geo, years = item.split()
        first, _, last = years.partition("-")
        cells |= {(geo, str(year)) for year in range(int(first), int(last or first) + 1)}
    return frozenset(cells)


def _pjanind(definition_id: str, code: str, **fixed: str) -> Series:
    return Series(
        "eurostat_demo_pjanind",
        definition_id,
        Nature.OFFICIAL_ESTIMATE,
        select={"indic_de": code},
        fixed=fixed,
    )


def _gind(definition_id: str, code: str) -> Series:
    return Series(
        "eurostat_demo_gind", definition_id, Nature.OFFICIAL_ESTIMATE, select={"indic_de": code}
    )


def _regional(source_id: str, definition_id: str, nature: Nature, **select: str) -> Series:
    """A Greek regional series (EL and its NUTS 1-3 codes, as the table has them)."""
    return Series(source_id, definition_id, nature, select=select, geo_prefix="EL")


def _find(definition_id: str, code: str) -> Series:
    return Series(
        "eurostat_demo_find", definition_id, Nature.OFFICIAL_ESTIMATE, select={"indic_de": code}
    )


def _pjanind2(definition_id: str, code: str, **fixed: str) -> Series:
    unit = "YR" if definition_id == "median_age@v1" else "PC"
    return Series(
        "eurostat_demo_r_pjanind2",
        definition_id,
        Nature.OFFICIAL_ESTIMATE,
        select={"indic_de": code, "unit": unit},
        fixed=fixed,
        geo_prefix="EL",
    )


_Y0_14, _Y15_64, _Y65_ = pl.col("y0_14"), pl.col("y15_64"), pl.col("y65_")
# Ratio indicators: numerator, denominator and the demo_pjanind(2) code.
_RATIOS = {
    "old_age_dependency_ratio": (_Y65_, _Y15_64, "OLDDEP1"),
    "young_age_dependency_ratio": (_Y0_14, _Y15_64, "YOUNGDEP1"),
    "total_age_dependency_ratio": (_Y0_14 + _Y65_, _Y15_64, "DEPRATIO1"),
    "ageing_index": (_Y65_, _Y0_14, None),
}
# demo_pjanind(2) has no PC_Y15_64; 15-64 is 100 minus the other two.
_SHARE_CODES = {"0-14": "PC_Y0_14", "65+": "PC_Y65_MAX", "80+": "PC_Y80_MAX"}
_MEDIAN_CODES = {"total": "MEDAGEPOP", "male": "MMEDAGEPOP", "female": "FMEDAGEPOP"}


def _structure(
    population: Series,
    broad: Series,
    official: Callable[..., Series],
    known: dict[str, str],
) -> dict[str, Indicator]:
    """#9-#12 from single ages in ``population``, compared with ``official`` and
    corroborated by the broad age groups in ``broad``."""

    def indicator(
        name: str, formula: Formula, broad_formula: Formula | None, compared: tuple[Series, ...]
    ) -> Indicator:
        definition_id, version = f"{name}@v1", f"{name}@0.1"
        corroboration = (
            (Indicator(definition_id, version, {"population": broad}, broad_formula),)
            if broad_formula
            else ()
        )
        return Indicator(
            definition_id,
            version,
            {"population": population},
            formula,
            official=compared,
            known_differences=_cells(known[name]) if name in known else frozenset(),
            corroboration=corroboration,
        )

    out = {
        name: indicator(
            name,
            _per_100(numerator, denominator),
            _per_100(numerator, denominator, _broad_groups),
            (official(f"{name}@v1", code),) if code else (),
        )
        for name, (numerator, denominator, code) in _RATIOS.items()
    }
    out["population_share"] = indicator(
        "population_share",
        _shares(_age_groups),
        _shares(_broad_groups),
        tuple(official("population_share@v1", c, age=band) for band, c in _SHARE_CODES.items()),
    )
    out["median_age"] = indicator(
        "median_age",
        _median_age,
        None,
        tuple(official("median_age@v1", c, sex=sex) for sex, c in _MEDIAN_CODES.items()),
    )
    return out


# Known differences: cells where the official structure indicators disagree with
# Eurostat's own population tables and no broad-group table can corroborate ours
# (checked 2026-09-29 on the tables of that date; corroborated differences are found by
# `grpop-build` itself). 80+ share: VERIFIED that demo_pjangroup (five-year
# groups) equals ours to every digit, except MD 2014, where demo_pjan, demo_pjangroup and
# demo_pjanind give three different values (2.1, 2.7, 2.4, the last flagged "e"; cause
# UNKNOWN). Median age: for AM 2024 demo_pjangroup gives 39.1 (ours 39.1, demo_pjanind
# 33.7); the other differences (at most 0.16) are in country-years whose ratios are
# corroborated, and five-year groups are too coarse to settle them. INFERENCE: the
# indicator tables were not recomputed after the populations were revised.
# `grpop-build` fails if a listed difference goes away.
_POPULATION = Series("eurostat_demo_pjan", "population_1jan@v1", Nature.OFFICIAL_ESTIMATE)
_POPULATION_REGIONAL = _regional(
    "eurostat_demo_r_d2jan", "population_1jan@v1", Nature.OFFICIAL_ESTIMATE
)
INDICATORS = {
    **_structure(
        _POPULATION,
        Series("eurostat_demo_pjanbroad", "population_1jan@v1", Nature.OFFICIAL_ESTIMATE),
        _pjanind,
        known={
            "population_share": "LT 2015-2020, IE 2012, MD 2014",
            "median_age": "LT 2015, LT 2017-2020, EE 2015, HR 2013, AM 2024, MD 2014",
        },
    ),
    # Greece and its NUTS 1-2 regions, from demo_r_d2jan. Same definitions; keys end in
    # _regional. Other countries' regions are out of scope (PROPOSAL §4).
    **{
        f"{name}_regional": indicator
        for name, indicator in _structure(
            _POPULATION_REGIONAL,
            _regional("eurostat_demo_r_pjanaggr3", "population_1jan@v1", Nature.OFFICIAL_ESTIMATE),
            _pjanind2,
            known={},
        ).items()
    },
    "population_growth_rate": Indicator(
        definition_id="population_growth_rate@v1",
        transform_version="population_growth_rate@0.1",
        inputs={
            "change": _gind("population_change@v1", "GROW"),
            "average": _gind("average_population@v1", "AVG"),
        },
        formula=_growth_rate,
        official=(_gind("population_growth_rate@v1", "GROWRT"),),
        # BA 2010 (demo_gind updated 2026-07-21): its own GROW / AVG is -0.22, its GROWRT -0.3.
        # Cause UNKNOWN.
        known_differences=_cells("BA 2010"),
    ),
    "total_fertility_rate": Indicator(
        definition_id="total_fertility_rate@v1",
        transform_version="total_fertility_rate@0.1",
        inputs={
            "rates": Series("eurostat_demo_frate", "fertility_rate@v1", Nature.OFFICIAL_ESTIMATE)
        },
        formula=_total_fertility,
        official=(_find("total_fertility_rate@v1", "TOTFERRT"),),
        decimals=2,
        input_rounding=len(_FERTILITY_AGES) * 0.5e-5,
        # VERIFIED 2026-09-29 (tables updated 2026-09-25): for these years demo_frate's own
        # TOTAL equals our sum within 0.0001, and demo_find TOTFERRT differs by up to 0.033.
        # INFERENCE: the two tables were built from different versions of the Italian data.
        known_differences=_cells("IT 1960-1966, IT 1968-1969, IT 1997-1998"),
    ),
    # Δ9h: Greece. VERIFIED 2026-10-09 (both tables updated 2026-09-16): 67 of 78 months
    # equal demo_mexrt to its decimal. The rest differ, cause UNKNOWN: by 0.1-0.3 in 2022
    # (5 months), and in 2026 by 0.4 (January-April, ours lower), 0.9 (May) and 2.5 (June,
    # whose last weeks are provisional). INFERENCE for 2026: weekly deaths revised after
    # demo_mexrt was computed.
    "excess_mortality": Indicator(
        definition_id="excess_mortality@v1",
        transform_version="excess_mortality@0.1",
        inputs={
            "deaths": Series(
                "eurostat_demo_r_mwk_ts", "deaths@v1", Nature.OBSERVED, geo_prefix="EL"
            )
        },
        formula=_excess_mortality,
        official=(
            Series(
                "eurostat_demo_mexrt",
                "excess_mortality@v1",
                Nature.OFFICIAL_ESTIMATE,
                geo_prefix="EL",
            ),
        ),
        known_differences=frozenset(
            ("EL", p)
            for p in (
                "2022-01",
                "2022-02",
                "2022-05",
                "2022-11",
                "2022-12",
                *(f"2026-{m:02d}" for m in range(1, 7)),
            )
        ),
    ),
    # Δ7. Eurostat publishes no sex ratio, so there is no official value to match.
    **{
        name: Indicator(
            definition_id="sex_ratio@v1",
            transform_version="sex_ratio@0.1",
            inputs={"population": population},
            formula=_sex_ratio,
        )
        for name, population in (
            ("sex_ratio", _POPULATION),
            ("sex_ratio_regional", _POPULATION_REGIONAL),
        )
    },
}


# Official series published as the source gives them (PROPOSAL §4 #1, #3, #4, #6-#8).
SERIES = {
    "population": _POPULATION,
    "natural_change": Series(
        "eurostat_demo_gind", "natural_change@v1", Nature.OBSERVED, select={"indic_de": "NATGROW"}
    ),
    "net_migration": _gind("net_migration@v1", "CNMIGRAT"),
    "mean_age_first_birth": _find("mean_age_first_birth@v1", "AGEMOTH1"),
    # Δ7: crude rates and the mean age at childbearing, national and regional.
    "mean_age_childbearing": _find("mean_age_childbearing@v1", "AGEMOTH"),
    "crude_birth_rate": _gind("crude_birth_rate@v1", "GBIRTHRT"),
    "crude_death_rate": _gind("crude_death_rate@v1", "GDEATHRT"),
    "crude_net_migration_rate": _gind("crude_net_migration_rate@v1", "CNMIGRATRT"),
    # Δ9c: first marriage by sex, and the age of leaving the parental household
    **{
        f"{name}_{sex}": Series(
            "eurostat_demo_nind",
            f"{name}@v1",
            Nature.OFFICIAL_ESTIMATE,
            select={"indic_de": code},
            fixed={"sex": sex},
        )
        for name, codes in (
            ("mean_age_first_marriage", {"female": "FAGEMAR1", "male": "MAGEMAR1"}),
            ("total_first_marriage_rate", {"female": "FMAR1CUM", "male": "MMAR1CUM"}),
        )
        for sex, code in codes.items()
    },
    "age_leaving_parental_home": Series(
        "eurostat_yth_demo_030", "age_leaving_parental_home@v1", Nature.OFFICIAL_ESTIMATE
    ),
    **{
        f"life_expectancy_{age}": Series(
            "eurostat_demo_mlexpec",
            "life_expectancy@v1",
            Nature.OFFICIAL_ESTIMATE,
            select={"age": code},
            fixed={"age": age},
        )
        for age, code in {"0": "Y_LT1", "65": "Y65"}.items()
    },
    "infant_mortality_rate": Series(
        "eurostat_demo_minfind",
        "infant_mortality_rate@v1",
        Nature.OFFICIAL_ESTIMATE,
        select={"indic_de": "INFMORRT"},
    ),
    # Δ7b: the Eurostat life table by single year of age and sex, Greece only.
    # ponytail: all countries would be about a million rows per series; add them
    # when a page compares mortality by age.
    **{
        name: Series(
            "eurostat_demo_mlifetable",
            f"{name}@v1",
            Nature.OFFICIAL_ESTIMATE,
            select={"indic_de": code},
            geo_prefix="EL",
            decimals=5,
        )
        for name, code in {
            "age_specific_death_rate": "DEATHRATE",
            "probability_of_dying": "PROBDEATH",
        }.items()
    },
    # Δ9l: migration flows by single year of age and sex, Greece only (ELSTAT gives
    # Eurostat ages only in completed years).
    **{
        name: Series(
            source,
            f"{name}@v1",
            Nature.OFFICIAL_ESTIMATE,
            select={"agedef": "COMPLET"},
            geo_prefix="EL",
        )
        for name, source in {
            "immigration": "eurostat_migr_imm8",
            "emigration": "eurostat_migr_emi2",
        }.items()
    },
    # Greek regional series (EL and NUTS 1-3 as each table has them). #6 has no regional
    # table: demo_r_find2 has no mean age at first birth. #2 and #5 are published, not
    # derived, here: VERIFIED 2026-09-29 that they cannot be reproduced from the
    # published regional inputs (all EU regions).
    # demo_r_gind3 has no average population, and GROW over the mean of the two
    # 1 January populations misses GROWRT in 326 of 46,359 cells (EL 2013 among them).
    # The demo_r_frate2 rates sum to demo_r_find2 TOTFERRT except in 406 of 11,862 cells
    # (up to 0.26), and demo_r_frate2's own TOTAL matches neither in 367 of them.
    "population_regional": _POPULATION_REGIONAL,
    # Five-year age groups of Greece and its NUTS 1-3 regions, for regional pyramids.
    "population_by_age_group_regional": _regional(
        "eurostat_demo_r_pjangrp3", "population_1jan@v1", Nature.OFFICIAL_ESTIMATE
    ),
    "population_growth_rate_regional": _regional(
        "eurostat_demo_r_gind3",
        "population_growth_rate@v1",
        Nature.OFFICIAL_ESTIMATE,
        indic_de="GROWRT",
    ),
    "natural_change_regional": _regional(
        "eurostat_demo_r_gind3", "natural_change@v1", Nature.OBSERVED, indic_de="NATGROW"
    ),
    "net_migration_regional": _regional(
        "eurostat_demo_r_gind3",
        "net_migration@v1",
        Nature.OFFICIAL_ESTIMATE,
        indic_de="CNMIGRAT",
    ),
    "total_fertility_rate_regional": _regional(
        "eurostat_demo_r_find2",
        "total_fertility_rate@v1",
        Nature.OFFICIAL_ESTIMATE,
        indic_de="TOTFERRT",
        unit="NR",
    ),
    **{
        f"life_expectancy_{age}_regional": Series(
            "eurostat_demo_r_mlifexp",
            "life_expectancy@v1",
            Nature.OFFICIAL_ESTIMATE,
            select={"age": code},
            fixed={"age": age},
            geo_prefix="EL",
        )
        for age, code in {"0": "Y_LT1", "65": "Y65"}.items()
    },
    "infant_mortality_rate_regional": _regional(
        "eurostat_demo_r_minfind", "infant_mortality_rate@v1", Nature.OFFICIAL_ESTIMATE
    ),
    "mean_age_childbearing_regional": _regional(
        "eurostat_demo_r_find2",
        "mean_age_childbearing@v1",
        Nature.OFFICIAL_ESTIMATE,
        indic_de="AGEMOTH",
        unit="YR",
    ),
    **{
        f"{name}_regional": _regional(
            "eurostat_demo_r_gind3", f"{name}@v1", Nature.OFFICIAL_ESTIMATE, indic_de=code
        )
        for name, code in (
            ("crude_birth_rate", "GBIRTHRT"),
            ("crude_death_rate", "GDEATHRT"),
            ("crude_net_migration_rate", "CNMIGRATRT"),
        )
    },
}


def compute(indicator: Indicator, data: Data) -> pl.DataFrame:
    """The indicator as validated observations with nature ``derived``."""
    if len({s.source_id for s in indicator.inputs.values()}) != 1:
        raise ValueError(f"{indicator.definition_id}: inputs must come from one source")
    result = indicator.formula({name: s.read(data) for name, s in indicator.inputs.items()})
    definition = get_definition(indicator.definition_id)
    return validate_observations(
        result.select(
            *KEY,
            *_CARRIED,
            metric=pl.lit(definition.metric),
            definition_id=pl.lit(definition.id),
            value=pl.col("value"),
            unit=pl.lit(definition.unit),
            transform_version=pl.lit(indicator.transform_version),
            nature=pl.lit(Nature.DERIVED.value),
            status=pl.when(pl.col("provisional"))
            .then(pl.lit(Status.PROVISIONAL.value))
            .otherwise(pl.lit(Status.FINAL.value)),
            break_in_series=pl.col("break_in_series"),
            scenario_id=pl.lit(None, dtype=pl.String),
            interval=pl.lit(None, dtype=pl.String),
        )
    )


def sources(indicator: Indicator) -> set[str]:
    """Registry ids of every source the indicator, its official values and its
    corroboration read."""
    series = [*indicator.inputs.values(), *indicator.official]
    return {s.source_id for s in series}.union(*(sources(c) for c in indicator.corroboration))


def read_official(indicator: Indicator, data: Data) -> pl.DataFrame:
    if not indicator.official:
        raise ValueError(f"{indicator.definition_id} has no official counterpart")
    return pl.concat(s.read(data) for s in indicator.official)


def disagreements(indicator: Indicator, ours: pl.DataFrame, data: Data) -> pl.DataFrame:
    """Rows where our value and the official one differ by more than the official rounding.

    Compared wherever both have a value. Returns KEY, ours, official, ``known`` (the
    country-year is in ``indicator.known_differences``) and ``corroborated`` (a
    corroborating indicator gives our value).
    """
    official = read_official(indicator, data).select(*KEY, official="value")
    known = pl.DataFrame(
        list(indicator.known_differences),
        schema={"geo_code": pl.String, "period": pl.String},
        orient="row",
    ).with_columns(known=pl.lit(True))
    half_unit = 0.5 * 10**-indicator.decimals + indicator.input_rounding + 1e-9
    rows = (
        ours.select(*KEY, ours="value")
        .join(official, on=KEY)
        .filter((pl.col("ours") - pl.col("official")).abs() > half_unit)
        .join(known, on=["geo_code", "period"], how="left")
        .with_columns(pl.col("known").fill_null(False), corroborated=pl.lit(False))
    )
    for other in indicator.corroboration:
        alt = compute(other, data).select(*KEY, alt="value")
        rows = (
            rows.join(alt, on=KEY, how="left")
            .with_columns(
                corroborated=pl.col("corroborated")
                | ((pl.col("alt") - pl.col("ours")).abs() < 1e-9).fill_null(False)
            )
            .drop("alt")
        )
    return rows


def check(
    indicator: Indicator, ours: pl.DataFrame, data: Data
) -> tuple[pl.DataFrame, list[tuple[str, str]]]:
    """Differences from the official value that are neither listed nor corroborated, and
    listed country-years that were compared but no longer differ or are now corroborated.
    """
    rows = disagreements(indicator, ours, data)
    cells = ["geo_code", "period"]
    official = read_official(indicator, data).filter(pl.col("value").is_not_null())
    compared = set(ours.join(official, on=KEY).select(cells).iter_rows())
    still = set(rows.filter(pl.col("known") & ~pl.col("corroborated")).select(cells).iter_rows())
    gone = (indicator.known_differences & compared) - still
    return rows.filter(~pl.col("known") & ~pl.col("corroborated")), sorted(gone)
