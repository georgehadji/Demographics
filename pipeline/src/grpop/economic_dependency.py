"""Economic old-age dependency ratio (Δ9o), Greece.

People aged 65 and over who are not in the labour force per 100 employed people aged
20-64: the population aged 65+ on 1 January (demo_pjanbroad) minus the labour force
aged 65+ (Labour Force Survey, lfsa_pganws ACT), over the employed aged 20-64
(lfsa_pganws EMP), the survey's thousands times 1,000.

The European Commission's 2024 Ageing Report (Institutional Paper 279, Table 3 and
Table II.1.62) gives Greece in 2022 an economic old-age dependency ratio of 56.2; this
gives 56.3 (VERIFIED 2026-10-10, the test checks it). INFERENCE: the report's population
is EUROPOP2023's, not demo_pjanbroad's. Its total economic dependency ratio (152.2)
comes out 1.8 apart and is not published here. The survey covers private households
only; the population does not. Eurostat publishes no such ratio. Greece only.
"""

from __future__ import annotations

import polars as pl

from grpop import reproduction
from grpop.definitions import get_definition
from grpop.indicators import Data, Series
from grpop.provenance import AGE_TOTAL, Nature, Sex, Status, validate_observations

GEO = "EL"
POPULATION = Series("eurostat_demo_pjanbroad", "population_1jan@v1", Nature.OFFICIAL_ESTIMATE)
LFS = "eurostat_lfsa_pganws"
ACTIVE = Series(
    LFS, "labour_force@v1", Nature.OFFICIAL_ESTIMATE, select={"citizen": "TOTAL", "wstatus": "ACT"}
)
EMPLOYED = Series(
    LFS, "employment@v1", Nature.OFFICIAL_ESTIMATE, select={"citizen": "TOTAL", "wstatus": "EMP"}
)
SOURCES = frozenset({POPULATION.source_id, LFS})
DEFINITION = "economic_old_age_dependency_ratio@v1"
TRANSFORM_VERSION = "economic_dependency@0.1"
THOUSAND = 1000


def _one(series: Series, age: str, data: Data) -> pl.DataFrame:
    """The value of one age group, both sexes, per period, with its provenance."""
    df = reproduction._read(series, data).filter(
        pl.col("sex") == Sex.TOTAL.value, pl.col("age") == age
    )
    return reproduction._year(df, pl.col("value").first(), 1)


def economic_old_age_dependency(data: Data) -> pl.DataFrame:
    """The ratio per year, as observations."""
    rows = reproduction._combine(
        _one(POPULATION, "65+", data),
        _one(ACTIVE, "65+", data).rename({"value": "active"}),
        _one(EMPLOYED, "20-64", data).rename({"value": "employed"}),
    ).with_columns(
        value=100
        * (pl.col("value") - THOUSAND * pl.col("active"))
        / (THOUSAND * pl.col("employed"))
    )
    definition = get_definition(DEFINITION)
    return validate_observations(
        rows.select(
            metric=pl.lit(definition.metric),
            definition_id=pl.lit(DEFINITION),
            geo_code=pl.lit(GEO),
            geo_vintage=pl.lit("NUTS2024"),
            period="period",
            sex=pl.lit(Sex.TOTAL.value),
            age=pl.lit(AGE_TOTAL),
            value="value",
            unit=pl.lit(definition.unit),
            **reproduction._tables(POPULATION.source_id, LFS),
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
        ).sort("period")
    )
