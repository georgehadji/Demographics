"""Provenance contract for every value the project publishes.

A value is one row of the long-format ``observations`` table. This module is the
only definition of its fields, vocabularies and key (ADR 0006); docs/PROPOSAL.md
§2 explains why they exist. Nothing may be published, charted or quoted unless it
passes ``validate_observations``.
"""

from __future__ import annotations

from enum import StrEnum

import pandera.polars as pa
import polars as pl
from pandera.api.polars.types import PolarsData


class Nature(StrEnum):
    """What kind of number a value is."""

    OBSERVED = "observed"  # census or complete registration count
    OFFICIAL_ESTIMATE = "official_estimate"  # estimate published by a statistical authority
    DERIVED = "derived"  # computed by this project from the above
    PROJECTED = "projected"  # official or own projection under a documented model
    SCENARIO = "scenario"  # consequence of user or analyst assumptions


class Status(StrEnum):
    """Publication state of a value, independent of its nature."""

    PROVISIONAL = "provisional"
    FINAL = "final"
    REVISED = "revised"
    NOT_AVAILABLE = "not_available"
    # A break in series is the separate boolean column ``break_in_series``: sources flag
    # a break together with a status (Eurostat "bp" = break + provisional).


class Sex(StrEnum):
    """Sex breakdown of a value. Totals are explicit, never null."""

    TOTAL = "total"
    MALE = "male"
    FEMALE = "female"


# Age breakdown of a value, in completed years: "total", "unknown", an exact age
# ("0"), an inclusive band ("15-64") or an open-ended band ("85+"). Parsers map
# source codes to this form (e.g. Eurostat Y_LT1 -> "0", Y_GE85 -> "85+").
AGE_TOTAL = "total"
AGE_PATTERN = r"^(" + AGE_TOTAL + r"|unknown|\d{1,3}(-\d{1,3}|\+)?)$"


# Columns that identify one published value. A second row with the same key is a
# revision and belongs in the history table, not in the current table.
OBSERVATION_KEY = (
    "metric",
    "definition_id",
    "geo_code",
    "geo_vintage",
    "period",
    "sex",
    "age",
    "source",
    "dataset_code",
    "vintage",
    "scenario_id",
)

# Format of a definition id, e.g. "population_1jan@v1". The definitions themselves
# live in definitions.yaml.
DEFINITION_ID_PATTERN = r"^[a-z0-9_]+@v\d+$"


class ObservationSchema(pa.DataFrameModel):
    """Schema of the long-format observations table."""

    metric: str = pa.Field(str_length={"min_value": 1})
    definition_id: str = pa.Field(str_matches=DEFINITION_ID_PATTERN)
    geo_code: str = pa.Field(str_length={"min_value": 2})
    geo_vintage: str = pa.Field(str_length={"min_value": 1})
    period: str = pa.Field(str_matches=r"^\d{4}(-\d{2}(-\d{2})?)?$")
    sex: str = pa.Field(isin=[s.value for s in Sex])
    age: str = pa.Field(str_matches=AGE_PATTERN)
    value: float = pa.Field(nullable=True)
    unit: str = pa.Field(str_length={"min_value": 1})
    source: str = pa.Field(str_length={"min_value": 1})
    dataset_code: str = pa.Field(str_length={"min_value": 1})
    source_url: str = pa.Field(str_startswith="https://")
    vintage: str = pa.Field(str_length={"min_value": 1})
    retrieved_at: pl.Datetime(time_zone="UTC") = pa.Field()  # type: ignore[valid-type]
    transform_version: str = pa.Field(str_length={"min_value": 1})
    nature: str = pa.Field(isin=[n.value for n in Nature])
    status: str = pa.Field(isin=[s.value for s in Status])
    break_in_series: bool = pa.Field()  # the series is not comparable across this period
    scenario_id: str = pa.Field(nullable=True)

    class Config:
        strict = True  # no undeclared columns
        coerce = False  # types must already be right; silent coercion hides pipeline bugs

    @pa.dataframe_check(error="value must be null exactly when status is not_available")
    @classmethod
    def value_matches_availability(cls, data: PolarsData) -> pl.LazyFrame:
        return data.lazyframe.select(
            pl.col("value").is_null() == (pl.col("status") == Status.NOT_AVAILABLE.value)
        )

    @pa.dataframe_check(error="scenario_id is required for scenarios and forbidden otherwise")
    @classmethod
    def scenario_id_only_for_scenarios(cls, data: PolarsData) -> pl.LazyFrame:
        return data.lazyframe.select(
            pl.col("scenario_id").is_not_null() == (pl.col("nature") == Nature.SCENARIO.value)
        )

    @pa.dataframe_check(error="age band must run from lower to higher age")
    @classmethod
    def age_band_ordered(cls, data: PolarsData) -> pl.LazyFrame:
        bounds = pl.col("age").str.extract_groups(r"^(\d+)-(\d+)$")
        low = bounds.struct.field("1").cast(pl.Int32)
        high = bounds.struct.field("2").cast(pl.Int32)
        return data.lazyframe.select((low < high).fill_null(True))

    @pa.dataframe_check(error="definition_id, metric and unit must match definitions.yaml")
    @classmethod
    def matches_definition(cls, data: PolarsData) -> pl.LazyFrame:
        from grpop.definitions import load_definitions  # it imports this module

        cols = ["definition_id", "metric", "unit"]
        known = pl.LazyFrame(
            [(d.id, d.metric, d.unit, True) for d in load_definitions().values()],
            schema=[*cols, "known"],
            orient="row",
        )
        return data.lazyframe.join(known, on=cols, how="left", maintain_order="left").select(
            pl.col("known").fill_null(False)
        )

    @pa.dataframe_check(error="duplicate observation key: revisions belong in history")
    @classmethod
    def unique_key(cls, data: PolarsData) -> pl.LazyFrame:
        return data.lazyframe.select(~pl.struct(list(OBSERVATION_KEY)).is_duplicated())


def validate_observations(df: pl.DataFrame) -> pl.DataFrame:
    """Validate an observations table and return it unchanged.

    Raises ``pandera.errors.SchemaErrors`` listing every failing rule, not only the first.
    """
    return ObservationSchema.validate(df, lazy=True)
