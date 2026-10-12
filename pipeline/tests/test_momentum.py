"""The momentum gate on Greece's rows of the WPP 2024 files (recorded 2026-10-12)."""

import numpy as np
import polars as pl
import pytest
from test_indicators import data

from grpop import momentum
from grpop.parse import un_wpp_csv
from grpop.provenance import validate_observations

FILES = {
    momentum.POPULATION: "un_wpp2024_population_by_sex_grc.csv.gz",
    momentum.BASE: "un_wpp2024_population_1jan_grc_2024.csv.gz",
    momentum.LIFE_TABLE: "un_wpp2024_life_table_female_grc_2023.csv.gz",
    momentum.FERTILITY: "un_wpp2024_fertility_by_age1_grc_momentum.csv.gz",
    momentum.INDICATORS: "un_wpp2024_indicators_medium_grc.csv.gz",
}
DATA = data(momentum.SOURCES, FILES)


def test_reproduces_the_momentum_variant():
    df = momentum.reproduce(DATA)
    assert (df["year"].min(), df["year"].max(), df.height) == (2024, 2100, 77)
    off = ((df["ours"] - df["theirs"]) / df["theirs"]).abs().max()
    assert off < 0.0008  # 0.073% observed


def _changed(monkeypatch, mortality=1.0, shift=0):
    inputs = momentum.inputs

    def changed(d):
        population, m, rates, boys = inputs(d)
        return population, m * mortality, {t: np.roll(r, shift) for t, r in rates.items()}, boys

    monkeypatch.setattr(momentum, "inputs", changed)


def test_lower_mortality_is_not_the_variant(monkeypatch):
    _changed(monkeypatch, mortality=0.97)  # 3% lower mortality
    with pytest.raises(ValueError, match="not reproduced"):
        momentum.reproduce(DATA)


def test_births_a_year_of_age_off_are_not_the_variant(monkeypatch):
    _changed(monkeypatch, shift=1)
    with pytest.raises(ValueError, match="not reproduced"):
        momentum.reproduce(DATA)


def test_momentum_observations():
    snap, raw = DATA[momentum.POPULATION]
    df = validate_observations(un_wpp_csv.momentum(snap, raw))
    el = df.filter(pl.col("period") == "2100")
    by = dict(zip(el["sex"], el["value"], strict=True))
    assert by == {"total": 8062709, "male": by["male"], "female": 4028421}
    assert by["male"] + by["female"] in (by["total"] - 1, by["total"], by["total"] + 1)
    assert set(df["scenario_id"]) == {"wpp2024_momentum"} and df.height == 77 * 3


def test_another_area_is_refused():
    with pytest.raises(ValueError, match="no rows"):
        un_wpp_csv.greece(b"LocID,Time\n4,2024\n", ["Time"])
