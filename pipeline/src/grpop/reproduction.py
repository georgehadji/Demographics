"""General fertility rate and gross and net reproduction rates (Δ9f), Greece.

- general fertility rate: live births at every age of the mother (demo_fagec) per 1,000
  women aged 15-49, the mean of 1 January of the year and of the next (demo_pjan);
- gross reproduction rate: the age-specific fertility rates (demo_frate, summed as the
  total fertility rate is, ``indicators._FERTILITY_AGES``) times the share of girls among
  the year's live births (demo_fasec), the same at every age of the mother;
- net reproduction rate: the same with each age's rate weighted by the person-years
  lived at that age per woman born, from the female probabilities of dying of the
  year's life table (demo_mlifetable): L(x) = (l(x) + l(x+1)) / 2, l(0) = 1. An open
  class (10-14, 50+) takes the mean over its single ages.

Eurostat publishes none of the three. UN WPP 2024 gives Greece in 2023 a net
reproduction rate of 0.6422 at a total fertility rate of 1.3336 (WPP2024 Demographic
Indicators, medium variant, read 2026-10-08), against 0.610 at Eurostat's 1.2605 here.
VERIFIED: relative to the total fertility rate the two agree within 0.5% (0.4816 against
0.4837), the share of girls (WPP sex ratio at birth 106.4, demo_fasec 0.4876) and the
survival differing slightly. INFERENCE: the difference in level is WPP's own estimate of
fertility. Published on the decision of the responsible editor (2026-10-08).
Each value combines tables: provenance per ADR 0009.
"""

from __future__ import annotations

import polars as pl

from grpop import birth_order, decompose
from grpop.definitions import get_definition
from grpop.indicators import _FERTILITY_AGES, SERIES, Data, Series
from grpop.provenance import AGE_TOTAL, Nature, Sex, Status, validate_observations
from grpop.sources.registry import get_source

GEO = "EL"
RATES = birth_order.RATES
GIRLS = Series(
    "eurostat_demo_fasec", "live_births@v1", Nature.OFFICIAL_ESTIMATE, select={"age": "TOTAL"}
)
DYING = SERIES["probability_of_dying"]
SOURCES = frozenset(
    {decompose.BIRTHS.source_id, decompose.WOMEN.source_id, RATES.source_id, GIRLS.source_id}
    | {DYING.source_id}
)
GFR = "general_fertility_rate@v1"
GRR = "gross_reproduction_rate@v1"
NRR = "net_reproduction_rate@v1"
TRANSFORM_VERSION = "reproduction_rates@0.1"
_LAST_AGE = max(max(ages) for ages in decompose.CLASSES.values())  # 54
_FLAGS = ["provisional", "break_in_series"]
_DATES = ["vintage", "retrieved_at"]
_PROVENANCE = ["source_url", *_FLAGS, *_DATES]


def _read(series: Series, data: Data) -> pl.DataFrame:
    return decompose._read(series, data)


def _year(df: pl.DataFrame, value: pl.Expr, n: int | None = None) -> pl.DataFrame:
    """One row per period: ``value`` aggregated in a fixed order (same bytes each build),
    the provenance combined; with ``n``, only periods with exactly ``n`` rows."""
    out = (
        df.sort("period", "age")
        .group_by("period", maintain_order=True)
        .agg(
            value=value,
            source_url=pl.col("source_url").first(),
            **{c: pl.col(c).any() for c in _FLAGS},
            **{c: pl.col(c).max() for c in _DATES},
            n=pl.len(),
        )
    )
    return (out.filter(pl.col("n") == n) if n else out).drop("n")


def _combine(first: pl.DataFrame, *others: pl.DataFrame) -> pl.DataFrame:
    """Join per-period frames; the first gives source_url (ADR 0009), flags and dates combine."""
    out = first
    for i, other in enumerate(others):
        out = out.join(other.drop("source_url"), on="period", suffix=f"_{i}")
        out = out.with_columns(
            **{c: pl.col(c) | pl.col(f"{c}_{i}") for c in _FLAGS},
            **{c: pl.max_horizontal(c, f"{c}_{i}") for c in _DATES},
        ).drop([f"{c}_{i}" for c in [*_FLAGS, *_DATES]])
    return out


def _share_of_girls(data: Data) -> pl.DataFrame:
    births = _read(GIRLS, data).filter(pl.col("age") == AGE_TOTAL)
    girls = births.filter(pl.col("sex") == Sex.FEMALE.value)
    total = births.filter(pl.col("sex") == Sex.TOTAL.value).select("period", total="value")
    return _year(
        girls.join(total, on="period"), (pl.col("value") / pl.col("total")).first(), 1
    ).rename({"value": "girls"})


def _person_years(data: Data) -> pl.DataFrame:
    """Female person-years lived at each age class per woman born, l(0) = 1."""
    q = _read(DYING, data).filter(pl.col("sex") == Sex.FEMALE.value)
    q = q.with_columns(x=pl.col("age").cast(pl.Int32, strict=False)).filter(
        pl.col("x") <= _LAST_AGE
    )
    complete = q.group_by("period").agg(n=pl.len()).filter(pl.col("n") == _LAST_AGE + 1)
    lived = (
        q.join(complete.select("period"), on="period")
        .sort("period", "x")
        .with_columns(after=(1 - pl.col("value")).cum_prod().over("period"))
        .with_columns(before=pl.col("after").shift(1, fill_value=1.0).over("period"))
        .with_columns(person_years=(pl.col("before") + pl.col("after")) / 2)
        .filter(pl.col("age").is_in(list(decompose._CLASS_OF)))
        .with_columns(age=pl.col("age").replace_strict(decompose._CLASS_OF))
    )
    return (
        lived.sort("period", "x")
        .group_by("period", "age", maintain_order=True)
        .agg(
            person_years=pl.col("person_years").mean(),
            source_url=pl.col("source_url").first(),
            **{c: pl.col(c).any() for c in _FLAGS},
            **{c: pl.col(c).max() for c in _DATES},
        )
    )


def _reproduction(data: Data) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Gross and net reproduction rates per period, every age class required."""
    rates = _read(RATES, data).filter(pl.col("age").is_in(list(_FERTILITY_AGES)))
    width = pl.col("age").replace_strict(_FERTILITY_AGES, return_dtype=pl.Float64)
    gross = _year(rates, (pl.col("value") * width).sum(), len(_FERTILITY_AGES))
    weighted = rates.join(
        _person_years(data).select("period", "age", "person_years"), on=["period", "age"]
    )
    net = _year(
        weighted, (pl.col("value") * width * pl.col("person_years")).sum(), len(_FERTILITY_AGES)
    )
    # the life table's provenance, per period
    life = _year(_person_years(data), pl.col("person_years").first())
    girls = _share_of_girls(data)
    times_girls = pl.col("value") * pl.col("girls")
    gross = _combine(gross, girls).with_columns(value=times_girls).drop("girls")
    net = _combine(net, girls, life.drop("value")).with_columns(value=times_girls).drop("girls")
    return gross, net


def _general_fertility(data: Data) -> pl.DataFrame:
    births = _year(
        _read(decompose.BIRTHS, data).filter(pl.col("age") == AGE_TOTAL),
        pl.col("value").first(),
        1,
    )
    ages = [str(a) for a in range(15, 50)]
    women = _year(
        decompose._women(data)
        .filter(pl.col("age").is_in(ages))
        .with_columns(source_url=pl.lit(None, dtype=pl.String)),
        pl.col("value").sum(),
        len(ages),
    )
    return (
        _combine(births, women.rename({"value": "women"}))
        .with_columns(value=1000 * pl.col("value") / pl.col("women"))
        .drop("women")
    )


def _tables(*source_ids: str) -> dict[str, pl.Expr]:
    tables = [get_source(s) for s in source_ids]
    return {
        "source": pl.lit(" + ".join(dict.fromkeys(t.provider for t in tables))),
        "dataset_code": pl.lit("+".join(t.dataset_code for t in tables)),
    }


def reproduction_rates(data: Data) -> pl.DataFrame:
    """The general fertility rate and both reproduction rates, as observations."""
    gross, net = _reproduction(data)
    rows = pl.concat(
        [
            _general_fertility(data).with_columns(
                definition_id=pl.lit(GFR),
                **_tables(decompose.BIRTHS.source_id, decompose.WOMEN.source_id),
            ),
            gross.with_columns(
                definition_id=pl.lit(GRR), **_tables(RATES.source_id, GIRLS.source_id)
            ),
            net.with_columns(
                definition_id=pl.lit(NRR),
                **_tables(RATES.source_id, GIRLS.source_id, DYING.source_id),
            ),
        ],
        how="diagonal",
    )
    definition = {d: get_definition(d) for d in (GFR, GRR, NRR)}
    return validate_observations(
        rows.select(
            metric=pl.col("definition_id").replace_strict(
                {k: d.metric for k, d in definition.items()}
            ),
            definition_id="definition_id",
            geo_code=pl.lit(GEO),
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
        ).sort("definition_id", "period")
    )
