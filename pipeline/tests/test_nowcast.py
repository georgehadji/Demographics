"""Births of the latest year from its published months (Δ9g), on the recorded demo_fmonth."""

import polars as pl
import pytest
from test_indicators import data

from grpop import nowcast as n

# ELSTAT natural movement 2025 (release of 2026-10-01, tests/fixtures/elstat_spo03_2025.pdf):
# 65,618 live births, 167 of them of residents abroad, whom Eurostat does not count.
ELSTAT_2025_RESIDENTS = 65_618 - 167


@pytest.fixture(scope="module")
def df():
    return n.births_nowcast(data(n.SOURCES))


def test_2025_from_nine_months(df):
    value = dict(df.select("interval", "value").iter_rows())
    # 2024 total times January-September 2025 over January-September 2024
    jan_sep_2025 = 5631 + 5126 + 5088 + 4802 + 5293 + 5343 + 6111 + 5693 + 5364
    jan_sep_2024 = 6265 + 5476 + 5519 + 5317 + 5153 + 5292 + 6081 + 5627 + 5802
    assert value[None] == pytest.approx(68_309 * jan_sep_2025 / jan_sep_2024)
    assert value[None] == pytest.approx(ELSTAT_2025_RESIDENTS, rel=0.001)  # out of sample
    assert value["80_lower"] < ELSTAT_2025_RESIDENTS < value["80_upper"]
    assert value["95_lower"] < value["80_lower"] < value[None] < value["80_upper"]
    assert value["80_upper"] < value["95_upper"]
    assert set(df["period"]) == {"2025"}
    assert set(df["status"]) == {"provisional"}  # the 2025 months are
    assert set(df["nature"]) == {"projected"}


def test_backtest_errors_shrink_with_more_months():
    errors = n.backtest(data(n.SOURCES))
    q = errors.group_by("k").agg(pl.col("error").abs().quantile(0.8)).sort("k")["error"]
    assert q[-1] < q[0] / 5
    assert errors["period"].min() == "1992"  # earlier years have births of unknown month


def test_nothing_to_estimate_once_the_total_is_published(monkeypatch):
    table = n._table

    def with_total(d):
        df = table(d)
        total = df.filter(pl.col("month") == "M01", pl.col("period") == "2025")
        return pl.concat([df, total.with_columns(month=pl.lit("TOTAL"), value=pl.lit(1.0))])

    monkeypatch.setattr(n, "_table", with_total)
    assert n.births_nowcast(data(n.SOURCES)).is_empty()
