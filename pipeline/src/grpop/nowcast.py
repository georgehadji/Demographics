"""Live births of the latest year estimated from its published months (Δ9g), Greece.

Eurostat's monthly births (demo_fmonth) come months before the year's total. For the
latest year t with its first k months published and no total yet:

    estimate = total(t-1) * births(t, months 1..k) / births(t-1, months 1..k)

that is, the remaining months change as the published ones did. ponytail: last year's
monthly pattern only; a mean of several years if the backtest ever says so.

Backtest (the published results this method must reproduce): for every past year whose
months and the year before's add up to the published total (no birth of unknown month),
and every k = 1..11, the estimate against the year's published total. The 80% and 95%
bounds are the estimate times 1 -/+ the 80th and 95th percentile of the absolute relative
error at the same k. Greece: 33 years (1992-2024), mean error within 0.4% at every k;
the 80% bound is +-6.4% with one month, +-1.3% with nine. INFERENCE: the past errors
stand for this year's.

Out of sample, VERIFIED (2026-10-08): with 9 months the 2025 estimate is 65,496; ELSTAT's
provisional 2025 total is 65,618 with 167 births of residents abroad, which Eurostat does
not count since 2022 (reconcile.py): 65,451 on Eurostat's basis; the estimate is 0.07%
above it.

When the latest year's total is published and no month of the next has been, there is
nothing to estimate and the step is empty.
"""

from __future__ import annotations

import polars as pl

from grpop.definitions import get_definition
from grpop.indicators import Data, Series
from grpop.provenance import AGE_TOTAL, Interval, Nature, Sex, Status, validate_observations

SOURCE = "eurostat_demo_fmonth"
DEFINITION = "live_births_nowcast@v1"
TRANSFORM_VERSION = "births_nowcast@0.1"
GEO = "EL"
MONTHS = [f"M{m:02d}" for m in range(1, 13)]
SOURCES = frozenset({SOURCE})
LEVELS = {80: (Interval.LOWER_80, Interval.UPPER_80), 95: (Interval.LOWER_95, Interval.UPPER_95)}
MIN_BACKTEST_YEARS = 10


def _table(data: Data) -> pl.DataFrame:
    """Greek births by year and month code (TOTAL, M01-M12, UNK), with provenance."""

    def one(code: str) -> pl.DataFrame:
        series = Series(SOURCE, "live_births@v1", Nature.OBSERVED, {"month": code}, geo_prefix=GEO)
        return series.read(data).with_columns(month=pl.lit(code))

    return (
        pl.concat([one(c) for c in ["TOTAL", *MONTHS, "UNK"]])
        .filter(pl.col("geo_code") == GEO, pl.col("value").is_not_null())
        .with_columns(provisional=pl.col("status") == Status.PROVISIONAL.value)
    )


def _years(table: pl.DataFrame) -> pl.DataFrame:
    """Per year: cumulative births of months 1..k (list of 12, null where unpublished)
    and the published total, or null; ``clean`` if the months add up to it."""
    months = (
        table.filter(pl.col("month").is_in(MONTHS))
        .sort("period", "month")
        .group_by("period", maintain_order=True)
        .agg(month=pl.col("month"), value=pl.col("value"))
    )
    total = table.filter(pl.col("month") == "TOTAL").select("period", total="value")
    unknown = table.filter(pl.col("month") == "UNK").select("period", unknown="value")
    rows = []
    for period, month, value in months.iter_rows():
        by_month = dict(zip(month, value, strict=True))
        cum: list[float | None] = []
        running: float | None = 0.0
        for m in MONTHS:
            if m not in by_month or running is None:
                running = None
            else:
                running += by_month[m]
            cum.append(running)
        rows.append((period, cum))
    df = pl.DataFrame(rows, schema={"period": pl.String, "cum": pl.List(pl.Float64)}, orient="row")
    return (
        df.join(total, on="period", how="left")
        .join(unknown, on="period", how="left")
        .with_columns(
            clean=(pl.col("cum").list.get(11) == pl.col("total"))
            & (pl.col("unknown").fill_null(0) == 0)
        )
        .sort("period")
    )


def _estimate(prev_total: pl.Expr, now: pl.Expr, before: pl.Expr) -> pl.Expr:
    return prev_total * now / before


def backtest(data: Data) -> pl.DataFrame:
    """Relative error of the estimate per past year and k: period, k, error."""
    years = _years(_table(data))
    pairs = years.join(
        years.select(
            period=(pl.col("period").cast(pl.Int32) + 1).cast(pl.String),
            prev_cum="cum",
            prev_total="total",
            prev_clean="clean",
        ),
        on="period",
    ).filter("clean", "prev_clean")
    return (
        pairs.with_columns(k=pl.lit(list(range(1, 12))))
        .explode("k", empty_as_null=True)
        .with_columns(
            estimate=_estimate(
                pl.col("prev_total"),
                pl.col("cum").list.get(pl.col("k") - 1),
                pl.col("prev_cum").list.get(pl.col("k") - 1),
            )
        )
        .select("period", "k", error=pl.col("estimate") / pl.col("total") - 1)
        .sort("k", "period")
    )


def births_nowcast(data: Data) -> pl.DataFrame:
    """The latest year's estimate and its 80% and 95% bounds, as observations."""
    table = _table(data)
    years = _years(table)
    latest = years.row(-1, named=True)
    previous = years.filter(pl.col("period") == str(int(latest["period"]) - 1))
    k = sum(c is not None for c in latest["cum"])
    if latest["total"] is not None or not 1 <= k <= 11 or previous.is_empty():
        return validate_observations(_empty(table))
    prev = previous.row(0, named=True)
    if not prev["clean"] or latest["cum"][k - 1] is None:
        raise ValueError(f"{SOURCE}: {latest['period']} cannot be estimated from {prev['period']}")
    central = prev["total"] * latest["cum"][k - 1] / prev["cum"][k - 1]
    errors = backtest(data).filter(pl.col("k") == k)["error"].abs()
    if errors.len() < MIN_BACKTEST_YEARS:
        raise ValueError(f"{SOURCE}: {errors.len()} backtest years for k={k}")
    values: dict[str | None, float] = {None: central}
    for level, (lower, upper) in LEVELS.items():
        q = errors.quantile(level / 100, interpolation="linear")
        if q is None:
            raise ValueError(f"{SOURCE}: no backtest error for k={k}")
        values |= {lower.value: central * (1 - q), upper.value: central * (1 + q)}
    used = table.filter(pl.col("period").is_in([latest["period"], prev["period"]]))
    return validate_observations(_rows(used, latest["period"], values))


def _rows(used: pl.DataFrame, period: str, values: dict[str | None, float]) -> pl.DataFrame:
    definition = get_definition(DEFINITION)
    provisional = used["provisional"].any()
    return pl.DataFrame(
        {"interval": list(values), "value": list(values.values())},
        schema={"interval": pl.String, "value": pl.Float64},
    ).select(
        metric=pl.lit(definition.metric),
        definition_id=pl.lit(DEFINITION),
        geo_code=pl.lit(GEO),
        geo_vintage=pl.lit("NUTS2024"),
        period=pl.lit(period),
        sex=pl.lit(Sex.TOTAL.value),
        age=pl.lit(AGE_TOTAL),
        value="value",
        unit=pl.lit(definition.unit),
        source=pl.lit(used["source"].first(), dtype=pl.String),
        dataset_code=pl.lit(used["dataset_code"].first(), dtype=pl.String),
        source_url=pl.lit(used["source_url"].first(), dtype=pl.String),
        vintage=pl.lit(used["vintage"].max(), dtype=pl.String),
        retrieved_at=pl.lit(used["retrieved_at"].max(), dtype=pl.Datetime("us", "UTC")),
        transform_version=pl.lit(TRANSFORM_VERSION),
        nature=pl.lit(Nature.PROJECTED.value),
        status=pl.lit(Status.PROVISIONAL.value if provisional else Status.FINAL.value),
        break_in_series=pl.lit(bool(used["break_in_series"].any())),
        scenario_id=pl.lit(None, dtype=pl.String),
        interval="interval",
    )


def _empty(table: pl.DataFrame) -> pl.DataFrame:
    return _rows(table, "2000", {}).clear()
