"""The cohort-component step and its gate, on Greece's recorded EUROPOP2025 baseline."""

import numpy as np
import polars as pl
import pytest
from test_indicators import data

from grpop import cohort

DATA = data(cohort.SOURCES, {cohort.POPULATION: "eurostat_proj_25np_el_bsl.json"})


def test_reproduces_the_baseline():
    df = cohort.reproduce(DATA)
    assert df["year"].unique().sort().to_list() == [2027, 2028, 2029, 2030, 2031]
    assert (df["ours"] - df["theirs"]).abs().max() <= 2
    totals = df.group_by("year").agg(pl.col("ours", "theirs").sum())
    assert (totals["ours"] - totals["theirs"]).abs().max() < 20  # 202 cells, each rounded


def test_boys_share_is_eurostats():
    assert round(cohort.boys_share(DATA), 4) == 0.513


def test_another_mortality_is_not_the_baseline(monkeypatch):
    table = cohort._table

    def higher(d, source_id):
        out = table(d, source_id)
        return {t: v * 1.01 for t, v in out.items()} if source_id == cohort.MORTALITY else out

    monkeypatch.setattr(cohort, "_table", higher)
    with pytest.raises(ValueError, match="not reproduced"):
        cohort.reproduce(DATA)


def test_without_events_cohorts_only_age():
    rng = np.random.default_rng(0)
    population = rng.integers(0, 1000, (2, cohort.OPEN + 1)).astype(float)
    zero = np.zeros((2, cohort.OPEN + 1))
    new, births = cohort.step(population, zero, zero, np.zeros(cohort.OPEN + 1), 0.5)
    assert births == 0 and new.sum() == population.sum()
    assert (new[:, 1:100] == population[:, :99]).all()
    assert (new[:, 0] == 0).all()
