"""Prospective old-age dependency (Δ9d): old age measured by remaining life expectancy.

The measures of Sanderson and Scherbov (2005, 2010), ``sanderson2005`` and
``sanderson2010`` in data/bibliography.

The old-age threshold of a sex and year is the age at which its remaining life
expectancy (Eurostat demo_mlifetable LIFEXP, period life table of the year) is 15 years,
interpolated linearly between the two single ages around it. The prospective old-age
dependency ratio is the people above the threshold per 100 people aged 20 to the
threshold, each sex with its own threshold, on 1 January of the year (demo_pjan); the
single age the threshold falls in is split in proportion. Greece only.

Reproduction (decision of the responsible editor, 2026-10-07, to publish on this):
VERIFIED, the thresholds: on the 2012 life table they are 69.3 (men) and 72.0 (women),
against 69.2 and 71.9 for 2010-15 in the IIASA Aging Demographic Data Sheet 2018.
Not reproduced, the ratio: the European Demographic Data Sheet 2014 gives 21.8 for Greece
in 2013 (2012 life table), this method 21.3 on today's data. INFERENCE: a population of
another vintage, as the same sheet's 65+/20-64 ratio is 33.4 against today's 33.0.

The ratio combines two tables, so its provenance follows ADR 0009.
"""

from __future__ import annotations

import polars as pl

from grpop.definitions import get_definition
from grpop.indicators import SERIES, Data, Series
from grpop.provenance import Nature, Sex, Status, validate_observations
from grpop.sources.registry import get_source

GEO = "EL"
LIFE_EXPECTANCY = Series(
    "eurostat_demo_mlifetable",
    "life_expectancy@v1",
    Nature.OFFICIAL_ESTIMATE,
    select={"indic_de": "LIFEXP"},
)
POPULATION = SERIES["population"]
SOURCES = frozenset({LIFE_EXPECTANCY.source_id, POPULATION.source_id})
THRESHOLD = "old_age_threshold@v1"
RATIO = "prospective_old_age_dependency_ratio@v1"
TRANSFORM_VERSION = "prospective_old_age_dependency@0.1"
REMAINING_YEARS = 15.0
_SEXES = [Sex.MALE.value, Sex.FEMALE.value]
_FLAGS = ["provisional", "break_in_series"]
_DATES = ["vintage", "retrieved_at"]


def _read(series: Series, data: Data) -> pl.DataFrame:
    return (
        series.read(data)
        .filter(
            pl.col("geo_code") == GEO,
            pl.col("sex").is_in(_SEXES),
            pl.col("value").is_not_null(),
        )
        .with_columns(
            provisional=pl.col("status") == Status.PROVISIONAL.value,
            # single ages; the open class (e.g. 100+) counts from its lower bound
            x=pl.col("age").str.strip_suffix("+").cast(pl.Int32, strict=False),
        )
        .filter(pl.col("x").is_not_null())
    )


def thresholds(data: Data) -> pl.DataFrame:
    """Per year and sex: the age at which remaining life expectancy is 15 years."""
    e = _read(LIFE_EXPECTANCY, data).filter(~pl.col("age").str.ends_with("+"))
    above = e.filter(pl.col("value") > REMAINING_YEARS)
    below = e.filter(pl.col("value") <= REMAINING_YEARS)
    last_above = above.group_by("period", "sex").agg(pl.all().sort_by("x").last())
    first_below = below.group_by("period", "sex").agg(pl.all().sort_by("x").first())
    both = last_above.join(first_below, on=["period", "sex"], suffix="_b").filter(
        pl.col("x_b") == pl.col("x") + 1  # e falls with age: the crossing is between them
    )
    return both.select(
        "period",
        "sex",
        "source_url",
        threshold=pl.col("x")
        + (pl.col("value") - REMAINING_YEARS) / (pl.col("value") - pl.col("value_b")),
        **{c: pl.col(c) | pl.col(f"{c}_b") for c in _FLAGS},
        **{c: pl.max_horizontal(c, f"{c}_b") for c in _DATES},
    )


def _ratio(data: Data, limits: pl.DataFrame) -> pl.DataFrame:
    """People above each sex's threshold per 100 aged 20 to it, both sexes together."""
    pop = _read(POPULATION, data).join(
        limits.select("period", "sex", "threshold"), on=["period", "sex"]
    )
    # the share of each single age [x, x+1) above the threshold
    above = pl.min_horizontal(1.0, pl.max_horizontal(0.0, pl.col("x") + 1 - pl.col("threshold")))
    open_class = pl.col("age").str.ends_with("+")
    old = (
        pl.when(open_class)
        .then((pl.col("x") >= pl.col("threshold")).cast(pl.Float64))
        .otherwise(above)
    )
    working = pl.when(pl.col("x") >= 20).then(1 - old).otherwise(0.0)
    return (
        pop.sort("period", "sex", "x")  # a float sum in a fixed order: same bytes each build
        .group_by("period", maintain_order=True)
        .agg(
            value=100 * (pl.col("value") * old).sum() / (pl.col("value") * working).sum(),
            **{c: pl.col(c).any() for c in _FLAGS},
            **{c: pl.col(c).max() for c in _DATES},
            n_sexes=pl.col("sex").n_unique(),
        )
        .filter(pl.col("n_sexes") == len(_SEXES))
        .join(
            limits.group_by("period").agg(
                pl.col("source_url").first().alias("table_url"),
                pl.col(*_FLAGS).any().name.suffix("_e"),
                pl.col(*_DATES).max().name.suffix("_e"),
                n_limits=pl.len(),
            ),
            on="period",
        )
        .filter(pl.col("n_limits") == len(_SEXES))
        .select(
            "period",
            "value",
            **{c: pl.col(c) | pl.col(f"{c}_e") for c in _FLAGS},
            **{c: pl.max_horizontal(c, f"{c}_e") for c in _DATES},
        )
    )


def prospective_old_age_dependency(data: Data) -> pl.DataFrame:
    """The thresholds by sex and the ratio, as observations."""
    limits = thresholds(data)
    ratio = _ratio(data, limits)
    pop_url = _read(POPULATION, data)["source_url"].first()
    life, pjan = get_source(LIFE_EXPECTANCY.source_id), get_source(POPULATION.source_id)
    rows = pl.concat(
        [
            limits.select(
                "period",
                "sex",
                "source_url",
                *_FLAGS,
                *_DATES,
                definition_id=pl.lit(THRESHOLD),
                value="threshold",
                source=pl.lit(life.provider),
                dataset_code=pl.lit(life.dataset_code),
            ),
            ratio.select(
                "period",
                *_FLAGS,
                *_DATES,
                sex=pl.lit(Sex.TOTAL.value),
                source_url=pl.lit(pop_url),
                definition_id=pl.lit(RATIO),
                value="value",
                # ADR 0009: the population first (numerator and denominator), then the table
                source=pl.lit(" + ".join(dict.fromkeys([pjan.provider, life.provider]))),
                dataset_code=pl.lit(f"{pjan.dataset_code}+{life.dataset_code}"),
            ),
        ],
        how="diagonal",  # by column name
    )
    definition = {d: get_definition(d) for d in (THRESHOLD, RATIO)}
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
            age=pl.lit("total"),
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
        ).sort("definition_id", "period", "sex")
    )
