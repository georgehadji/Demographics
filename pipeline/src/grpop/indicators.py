"""Indicators: specification, computation and agreement with the official value (ADR 0005, L4).

Each indicator is one ``Indicator`` entry in ``INDICATORS``: its definition (meaning
and unit, in definitions.yaml), its input series, a Polars formula and, where an
official source publishes the same indicator, that series. Acceptance tests are
generated from ``INDICATORS`` (tests/test_indicators.py): every indicator with an
official counterpart must agree with it within the official rounding.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import polars as pl

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

    def read(self, data: Data) -> pl.DataFrame:
        snapshot, raw = data[self.source_id]
        return eurostat.to_observations(
            snapshot,
            raw,
            definition_id=self.definition_id,
            nature=self.nature,
            geo_vintage=self.geo_vintage,
            select=self.select or None,
        )


@dataclass(frozen=True)
class Indicator:
    definition_id: str  # meaning and unit
    transform_version: str  # changes whenever the formula changes
    inputs: dict[str, Series]
    # Input observations by name -> KEY + value + provisional + break_in_series + _CARRIED.
    formula: Callable[[dict[str, pl.DataFrame]], pl.DataFrame]
    official: Series | None = None
    decimals: int = 1  # rounding of the official value


def carried() -> list[pl.Expr]:
    """Aggregations a formula adds to its group_by: status and provenance of the inputs.

    ponytail: provenance is copied from the single input series. An indicator with
    inputs from several datasets needs a provenance rule of its own.
    """
    return [
        (pl.col("status") == Status.PROVISIONAL.value).any().alias("provisional"),
        pl.col("break_in_series").any(),
        *(pl.col(c).first() for c in _CARRIED),
    ]


def _old_age_dependency(inputs: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """65+ per 100 aged 15-64. 65+ is total minus unknown minus ages 0-64, so the
    open-ended age class is not needed; computed only where ages 0-64 are complete."""
    pop = inputs["population"].filter(pl.col("value").is_not_null())
    age = pl.col("age").cast(pl.Int32, strict=False)  # null for total, unknown, bands, N+
    value = pl.col("value")
    return (
        pop.group_by("geo_code", "period", "sex")
        .agg(
            *carried(),
            total=value.filter(pl.col("age") == "total").first(),
            unknown=value.filter(pl.col("age") == "unknown").sum(),
            young=value.filter(age < 15).sum(),
            working=value.filter(age.is_between(15, 64)).sum(),
            single_ages=value.filter(age <= 64).len(),
        )
        .filter((pl.col("single_ages") == 65) & pl.col("total").is_not_null())
        .with_columns(
            age=pl.lit("total"),
            value=(pl.col("total") - pl.col("unknown") - pl.col("young") - pl.col("working"))
            / pl.col("working")
            * 100,
        )
    )


_POPULATION = Series("eurostat_demo_pjan", "population_1jan@v1", Nature.OFFICIAL_ESTIMATE)

INDICATORS = {
    "old_age_dependency_ratio": Indicator(
        definition_id="old_age_dependency_ratio@v1",
        transform_version="old_age_dependency_ratio@0.1",
        inputs={"population": _POPULATION},
        formula=_old_age_dependency,
        official=Series(
            "eurostat_demo_pjanind",
            "old_age_dependency_ratio@v1",
            Nature.OFFICIAL_ESTIMATE,
            select={"indic_de": "OLDDEP1"},
        ),
    ),
}


def compute(indicator: Indicator, data: Data) -> pl.DataFrame:
    """The indicator as validated observations with nature ``derived``."""
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


def disagreements(indicator: Indicator, ours: pl.DataFrame, data: Data) -> pl.DataFrame:
    """Rows where our value and the official one differ by more than the official rounding.

    Compared wherever both have a value. Returns KEY, ours, official.
    """
    if indicator.official is None:
        raise ValueError(f"{indicator.definition_id} has no official counterpart")
    official = indicator.official.read(data).select(*KEY, official="value")
    half_unit = 0.5 * 10**-indicator.decimals + 1e-9
    return (
        ours.select(*KEY, ours="value")
        .join(official, on=KEY)
        .filter((pl.col("ours") - pl.col("official")).abs() > half_unit)
    )
