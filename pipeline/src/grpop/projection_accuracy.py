"""Deviation of earlier Eurostat projections from the observed population (Δ9e).

The baseline of each earlier EUROPOP still in the Eurostat database (EUROPOP2019 and
EUROPOP2023; the older ones are no longer there) against today's population on
1 January (demo_pjan), in every area both publish:

- level: projected minus observed, as % of observed. In the projection's base year it
  is the revision of the base population after the projection was made;
- change: projected change since the base year minus observed change, as % of the
  observed base population. It leaves the revision out: the deviation of the
  projection's own assumptions.

A projection is a consequence of its assumptions, not a forecast. Greece: EUROPOP2019
started from 10,724,599 on 1 January 2019, demo_pjan now gives 10,635,213 (-0.8%).
INFERENCE: the revision after the 2021 census. No published evaluation of these
projections was found to reproduce (UNKNOWN whether one exists); the values are plain
differences of two published series. Each value combines two tables (ADR 0009).
"""

from __future__ import annotations

import polars as pl

from grpop.definitions import get_definition
from grpop.indicators import SERIES, Data, Series
from grpop.provenance import AGE_TOTAL, Nature, Sex, Status, validate_observations
from grpop.sources.registry import get_source

VINTAGES = ("eurostat_proj_19np", "eurostat_proj_23np")
POPULATION = SERIES["population"]
SOURCES = frozenset({*VINTAGES, POPULATION.source_id})
LEVEL = "projection_deviation_level@v1"
CHANGE = "projection_deviation_change@v1"
TRANSFORM_VERSION = "projection_accuracy@0.1"
BASELINE = "BSL"
_COLUMNS = ["geo_code", "period", "value", "source_url", "vintage", "retrieved_at"]


def _totals(series: Series, data: Data) -> pl.DataFrame:
    return (
        series.read(data)
        .filter(
            pl.col("sex") == Sex.TOTAL.value,
            pl.col("age") == AGE_TOTAL,
            pl.col("value").is_not_null(),
        )
        .select(
            *_COLUMNS,
            provisional=pl.col("status") == Status.PROVISIONAL.value,
            break_in_series="break_in_series",
        )
    )


def _deviations(source_id: str, data: Data, observed: pl.DataFrame) -> pl.DataFrame:
    """Both definitions for one projection, wherever the observed population exists."""
    projected = _totals(
        Series(source_id, "population_1jan@v1", Nature.PROJECTED, {"projection": BASELINE}), data
    )
    base_year = projected["period"].min()
    both = projected.join(observed, on=["geo_code", "period"], suffix="_o")
    base = both.filter(pl.col("period") == base_year).select(
        "geo_code",
        p0="value",
        o0="value_o",
        flag0=pl.col("provisional") | pl.col("provisional_o"),
        break0=pl.col("break_in_series") | pl.col("break_in_series_o"),
    )
    rows = both.join(base, on="geo_code").with_columns(
        provisional=pl.col("provisional") | pl.col("provisional_o"),
        break_in_series=pl.col("break_in_series") | pl.col("break_in_series_o"),
        vintage=pl.max_horizontal("vintage", "vintage_o"),
        retrieved_at=pl.max_horizontal("retrieved_at", "retrieved_at_o"),
    )
    keep = ["geo_code", "period", "source_url", "vintage", "retrieved_at"]
    level = rows.select(
        *keep,
        "provisional",
        "break_in_series",
        definition_id=pl.lit(LEVEL),
        value=100 * (pl.col("value") - pl.col("value_o")) / pl.col("value_o"),
    )
    change = rows.filter(pl.col("period") > base_year).select(
        *keep,
        provisional=pl.col("provisional") | pl.col("flag0"),
        break_in_series=pl.col("break_in_series") | pl.col("break0"),
        definition_id=pl.lit(CHANGE),
        value=100
        * ((pl.col("value") - pl.col("p0")) - (pl.col("value_o") - pl.col("o0")))
        / pl.col("o0"),
    )
    proj, pjan = get_source(source_id), get_source(POPULATION.source_id)
    return pl.concat([level, change]).with_columns(
        # ADR 0009: the projection first, it is what is measured
        source=pl.lit(" + ".join(dict.fromkeys([proj.provider, pjan.provider]))),
        dataset_code=pl.lit(f"{proj.dataset_code}+{pjan.dataset_code}"),
    )


def projection_accuracy(data: Data) -> pl.DataFrame:
    """Both deviations of every earlier projection, as observations."""
    observed = _totals(POPULATION, data)
    rows = pl.concat([_deviations(s, data, observed) for s in VINTAGES])
    definition = {d: get_definition(d) for d in (LEVEL, CHANGE)}
    return validate_observations(
        rows.select(
            metric=pl.col("definition_id").replace_strict(
                {k: d.metric for k, d in definition.items()}
            ),
            definition_id="definition_id",
            geo_code="geo_code",
            geo_vintage=pl.lit("NUTS2024"),
            period="period",
            sex=pl.lit(Sex.TOTAL.value),
            age=pl.lit(AGE_TOTAL),
            value="value",
            unit=pl.col("definition_id").replace_strict({k: d.unit for k, d in definition.items()}),
            source="source",
            dataset_code="dataset_code",
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
        ).sort("dataset_code", "definition_id", "geo_code", "period")
    )
