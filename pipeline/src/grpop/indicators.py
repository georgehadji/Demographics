"""Indicators: specification, computation and agreement with the official value (ADR 0005, L4).

Each indicator is one ``Indicator`` entry in ``INDICATORS``: its definition (meaning
and unit, in definitions.yaml), its input series, a Polars formula and, where an
official source publishes the same indicator, that series. Acceptance tests are
generated from ``INDICATORS`` (tests/test_indicators.py): every indicator with an
official counterpart must agree with it within the official rounding.
``grpop-check-indicators --store DIR`` runs the same comparison on every country and
year in a snapshot store. ``SERIES`` lists the official series published as the source
gives them.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from grpop import snapshots
from grpop.definitions import get_definition
from grpop.parse import eurostat
from grpop.provenance import Nature, Status, validate_observations
from grpop.snapshots import Snapshot

# Snapshot and bytes per registry source id, as the build reads them from the store.
Data = Mapping[str, tuple[Snapshot, bytes]]
KEY = ["geo_code", "period", "sex", "age"]
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

    def read(self, data: Data) -> pl.DataFrame:
        snapshot, raw = data[self.source_id]
        obs = eurostat.to_observations(
            snapshot,
            raw,
            definition_id=self.definition_id,
            nature=self.nature,
            geo_vintage=self.geo_vintage,
            select=self.select or None,
        )
        return obs.with_columns(**{k: pl.lit(v) for k, v in self.fixed.items()})


@dataclass(frozen=True)
class Indicator:
    definition_id: str  # meaning and unit
    transform_version: str  # changes whenever the formula changes
    inputs: dict[str, Series]
    # Input observations by name -> KEY + value + provisional + break_in_series + _CARRIED.
    formula: Callable[[dict[str, pl.DataFrame]], pl.DataFrame]
    official: tuple[Series, ...] = ()  # the same indicator as an official source publishes it
    decimals: int = 1  # rounding of the official value
    # Rounding error our value inherits from rounded inputs, added to the comparison
    # tolerance (e.g. a sum of 37 rates published to 5 decimals: 37 * 0.000005).
    input_rounding: float = 0.0
    # (geo_code, period) where the official value is known to differ from ours. Each set
    # is explained, with its evidence, where it is defined.
    known_differences: frozenset[tuple[str, str]] = frozenset()


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


def _per_100(
    numerator: pl.Expr, denominator: pl.Expr
) -> Callable[[dict[str, pl.DataFrame]], pl.DataFrame]:
    def formula(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
        return (
            _age_groups(inputs)
            .with_columns(age=pl.lit("total"), value=numerator / denominator * 100)
            .filter(pl.col("value").is_not_null())
        )

    return formula


_SHARES = {"0-14": "y0_14", "15-64": "y15_64", "65+": "y65_", "80+": "y80_"}


def _shares(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    groups = _age_groups(inputs)
    return pl.concat(
        groups.with_columns(age=pl.lit(band), value=pl.col(group) / pl.col("known") * 100)
        for band, group in _SHARES.items()
    ).filter(pl.col("value").is_not_null())


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


def _find(definition_id: str, code: str) -> Series:
    return Series(
        "eurostat_demo_find", definition_id, Nature.OFFICIAL_ESTIMATE, select={"indic_de": code}
    )


# Known differences below, checked 2026-09-29 against the tables updated 2026-09-25.
# They are cells where demo_pjanind disagrees with Eurostat's own population tables.
# VERIFIED: in these country-years, the dependency ratios and the 0-14 and 65+ shares
# computed from demo_pjanbroad (broad age groups), and the 80+ share from demo_pjangroup
# (five-year groups), equal ours to every digit. For AM 2024, the median age from
# demo_pjangroup is 39.1 (ours 39.1, demo_pjanind 33.7). The other median-age
# differences (at most 0.16) are in the same country-years; five-year groups are too
# coarse to settle them. INFERENCE: demo_pjanind was not recomputed after these
# populations were revised. MD 2014 is different: demo_pjan, demo_pjangroup and
# demo_pjanind give three different 80+ shares (2.1, 2.7, 2.4, the last flagged "e");
# the cause is UNKNOWN. `grpop-check-indicators` fails if a listed difference goes away.
_POPULATION = Series("eurostat_demo_pjan", "population_1jan@v1", Nature.OFFICIAL_ESTIMATE)
_Y0_14, _Y15_64, _Y65_ = pl.col("y0_14"), pl.col("y15_64"), pl.col("y65_")

INDICATORS = {
    "old_age_dependency_ratio": Indicator(
        definition_id="old_age_dependency_ratio@v1",
        transform_version="old_age_dependency_ratio@0.1",
        inputs={"population": _POPULATION},
        formula=_per_100(_Y65_, _Y15_64),
        official=(_pjanind("old_age_dependency_ratio@v1", "OLDDEP1"),),
        known_differences=_cells("LT 2015-2020, IE 2012-2013, EE 2020, HR 2013, MT 1995"),
    ),
    "young_age_dependency_ratio": Indicator(
        definition_id="young_age_dependency_ratio@v1",
        transform_version="young_age_dependency_ratio@0.1",
        inputs={"population": _POPULATION},
        formula=_per_100(_Y0_14, _Y15_64),
        official=(_pjanind("young_age_dependency_ratio@v1", "YOUNGDEP1"),),
        known_differences=_cells("LT 2015, IE 2012-2013"),
    ),
    "total_age_dependency_ratio": Indicator(
        definition_id="total_age_dependency_ratio@v1",
        transform_version="total_age_dependency_ratio@0.1",
        inputs={"population": _POPULATION},
        formula=_per_100(_Y0_14 + _Y65_, _Y15_64),
        official=(_pjanind("total_age_dependency_ratio@v1", "DEPRATIO1"),),
        known_differences=_cells(
            "LT 2015-2020, IE 2012-2013, EE 2015, HR 2013, EA20 2020, EU27_2007 2016"
        ),
    ),
    "ageing_index": Indicator(
        definition_id="ageing_index@v1",
        transform_version="ageing_index@0.1",
        inputs={"population": _POPULATION},
        formula=_per_100(_Y65_, _Y0_14),
    ),
    "population_share": Indicator(
        definition_id="population_share@v1",
        transform_version="population_share@0.1",
        inputs={"population": _POPULATION},
        formula=_shares,
        official=tuple(
            _pjanind("population_share@v1", code, age=band)
            # demo_pjanind has no PC_Y15_64; 15-64 is 100 minus the other two.
            for band, code in {
                "0-14": "PC_Y0_14",
                "65+": "PC_Y65_MAX",
                "80+": "PC_Y80_MAX",
            }.items()
        ),
        known_differences=_cells(
            "LT 2015-2020, IE 2012-2013, EE 2015, HR 2013, EA20 2020, MD 2014"
        ),
    ),
    "median_age": Indicator(
        definition_id="median_age@v1",
        transform_version="median_age@0.1",
        inputs={"population": _POPULATION},
        formula=_median_age,
        official=(
            _pjanind("median_age@v1", "MEDAGEPOP"),
            _pjanind("median_age@v1", "MMEDAGEPOP", sex="male"),
            _pjanind("median_age@v1", "FMEDAGEPOP", sex="female"),
        ),
        known_differences=_cells("LT 2015, LT 2017-2020, EE 2015, HR 2013, AM 2024, MD 2014"),
    ),
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
}


# Official series published as the source gives them (PROPOSAL §4 #1, #3, #4, #6-#8).
SERIES = {
    "population": _POPULATION,
    "natural_change": Series(
        "eurostat_demo_gind", "natural_change@v1", Nature.OBSERVED, select={"indic_de": "NATGROW"}
    ),
    "net_migration": _gind("net_migration@v1", "CNMIGRAT"),
    "mean_age_first_birth": _find("mean_age_first_birth@v1", "AGEMOTH1"),
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
        )
    )


def read_official(indicator: Indicator, data: Data) -> pl.DataFrame:
    if not indicator.official:
        raise ValueError(f"{indicator.definition_id} has no official counterpart")
    return pl.concat(s.read(data) for s in indicator.official)


def disagreements(indicator: Indicator, ours: pl.DataFrame, data: Data) -> pl.DataFrame:
    """Rows where our value and the official one differ by more than the official rounding.

    Compared wherever both have a value. Returns KEY, ours, official and ``known``
    (the country-year is in ``indicator.known_differences``).
    """
    official = read_official(indicator, data).select(*KEY, official="value")
    known = pl.DataFrame(
        list(indicator.known_differences), schema=["geo_code", "period"], orient="row"
    ).with_columns(known=pl.lit(True))
    half_unit = 0.5 * 10**-indicator.decimals + indicator.input_rounding + 1e-9
    return (
        ours.select(*KEY, ours="value")
        .join(official, on=KEY)
        .filter((pl.col("ours") - pl.col("official")).abs() > half_unit)
        .join(known, on=["geo_code", "period"], how="left")
        .with_columns(pl.col("known").fill_null(False))
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare every indicator with its official counterpart, on the "
        "latest snapshot of each source in a store. Fails on a difference that is not "
        "a known difference, and on a known difference that has gone away."
    )
    parser.add_argument("--store", type=Path, required=True)
    store = parser.parse_args(argv).store
    failed = False
    for name, indicator in INDICATORS.items():
        if not indicator.official:
            continue
        ids = {s.source_id for s in (*indicator.inputs.values(), *indicator.official)}
        data = {}
        for source_id in ids:
            snapshot = snapshots.history(store, source_id)[-1]
            data[source_id] = (snapshot, snapshots.read(store, snapshot.sha256))
        rows = disagreements(indicator, compute(indicator, data), data)
        unexplained = rows.filter(~pl.col("known"))
        gone = indicator.known_differences - set(
            rows.filter("known").select("geo_code", "period").iter_rows()
        )
        print(f"{name}: {unexplained.height} unexplained, {len(gone)} known gone")
        if unexplained.height or gone:
            failed = True
            with pl.Config(tbl_rows=-1):
                print(unexplained)
            print(sorted(gone))
    return 1 if failed else 0
