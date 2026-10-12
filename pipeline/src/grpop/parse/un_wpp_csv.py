"""UN WPP 2024 standard CSV files (gzip): Greece's rows, and the Momentum variant of the
total population as observations.

The files cover every area and, where they have them, every projection variant; rows
are kept by the UN's location code. Values are thousands; 1 July values are the mean
of two 1 January values (VERIFIED 2026-10-12, Greece 1950-2099, to 0.5 persons).
"""

from __future__ import annotations

import polars as pl

from grpop.definitions import get_definition
from grpop.provenance import AGE_TOTAL, Nature, Sex, Status
from grpop.snapshots import Snapshot
from grpop.sources.registry import get_source

GREECE = "300"  # UN M49 location code
DEFINITION_ID = "population_1jul@v1"
TRANSFORM_VERSION = "un_wpp_csv@0.1"
VINTAGE = "WPP 2024"
MOMENTUM = "Momentum"
SCENARIO_ID = "wpp2024_momentum"  # ADR 0008: a source's own variant, labelled as such
_SEXES = {"PopTotal": Sex.TOTAL, "PopMale": Sex.MALE, "PopFemale": Sex.FEMALE}


def greece(data: bytes, columns: list[str]) -> pl.DataFrame:
    """Greece's rows of a WPP CSV file, ``columns`` only, all as strings."""
    df = pl.read_csv(data, columns=["LocID", *columns], infer_schema_length=0)
    df = df.filter(pl.col("LocID") == GREECE).drop("LocID")
    if df.is_empty():
        raise ValueError(f"no rows of LocID {GREECE}")
    return df


def momentum(snapshot: Snapshot, data: bytes) -> pl.DataFrame:
    """Greece's population on 1 July in WPP 2024's Momentum variant, by sex."""
    definition, source = get_definition(DEFINITION_ID), get_source(snapshot.source_id)
    df = greece(data, ["Variant", "Time", *_SEXES]).filter(pl.col("Variant") == MOMENTUM)
    return (
        df.unpivot(list(_SEXES), index="Time", variable_name="column", value_name="value")
        .with_columns(
            sex=pl.col("column").replace_strict({c: s.value for c, s in _SEXES.items()}),
            value=(pl.col("value").cast(pl.Float64) * 1000).round(0),
        )
        .select(
            metric=pl.lit(definition.metric),
            definition_id=pl.lit(definition.id),
            geo_code=pl.lit("EL"),
            geo_vintage=pl.lit("ISO 3166-1"),
            period="Time",
            sex="sex",
            age=pl.lit(AGE_TOTAL),
            value="value",
            unit=pl.lit(definition.unit),
            source=pl.lit(source.provider),
            dataset_code=pl.lit(source.dataset_code),
            source_url=pl.lit(snapshot.source_url),
            vintage=pl.lit(VINTAGE),
            retrieved_at=pl.lit(snapshot.retrieved_at, dtype=pl.Datetime("us", "UTC")),
            transform_version=pl.lit(TRANSFORM_VERSION),
            nature=pl.lit(Nature.SCENARIO.value),
            status=pl.lit(Status.FINAL.value),
            break_in_series=pl.lit(False),
            scenario_id=pl.lit(SCENARIO_ID),
            interval=pl.lit(None, dtype=pl.String),
        )
    )
