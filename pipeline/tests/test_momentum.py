"""The momentum gate on Greece's rows of the WPP 2024 files (recorded 2026-10-12)."""

import numpy as np
import polars as pl
import pytest
from test_indicators import data

from grpop import momentum, reproduction
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


# Greece's own, from the recorded Eurostat tables (2023 and 2024 complete)
EUROSTAT = data(momentum.EUROSTAT_SOURCES | reproduction.SOURCES)
YEARS = momentum.inputs_eurostat(EUROSTAT)


def test_every_complete_year_and_only_those():
    assert list(YEARS) == [2023, 2024]


@pytest.mark.parametrize("year", [2023, 2024])
def test_stationary_population_per_birth_is_the_life_expectancy(year):
    y = YEARS[year]
    life = momentum._raw(EUROSTAT, momentum.DYING.source_id).filter(
        pl.col("time") == str(year), pl.col("age") == "Y_LT1"
    )
    cells = {(i, s): v for i, s, v in life.select("indic_de", "sex", "value").iter_rows()}
    e0 = np.array([cells["TOTPYLIVED", s] / cells["SURVIVORS", s] for s in "MF"])
    population, births = momentum.stationary(y, y.fertility / momentum.net_reproduction(y))
    per_birth = population.sum(1) / (births * np.array([y.boys, 1 - y.boys]))
    assert np.abs(per_birth / e0 - 1).max() < 1e-6


def test_net_reproduction_is_the_published_one():
    nrr = reproduction.reproduction_rates(EUROSTAT).filter(
        pl.col("definition_id") == reproduction.NRR
    )
    theirs = dict(nrr.select("period", "value").iter_rows())
    for year, y in YEARS.items():
        assert abs(momentum.net_reproduction(y) - theirs[str(year)]) < 1e-4  # 1e-5 observed


def test_constant_rates_grow_at_the_intrinsic_rate():
    y = YEARS[2024]
    growth, population, zero = momentum.intrinsic_growth(y), y.population, np.zeros((2, 101))
    for _ in range(1500):
        new, _ = momentum.step(population, y.mortality, zero, y.fertility, y.boys)
        ratio, population = new.sum() / population.sum(), new
    assert abs(ratio - growth) < 1e-9


def test_momentum_and_intrinsic_rate_of_greece():
    df = momentum.momentum(EUROSTAT)
    by = {
        (d, p, s): v
        for d, p, s, v in df.select("definition_id", "period", "sex", "value").iter_rows()
    }
    assert round(by[momentum.MOMENTUM_ID, "2024", "female"], 3) == 0.771
    assert 0.7 < by[momentum.MOMENTUM_ID, "2024", "total"] < 1
    assert -2 < by[momentum.INTRINSIC_ID, "2024", "total"] < -1
    assert set(df["nature"]) == {"derived"} and df.height == 2 * 4


def test_a_projection_that_never_settles_raises(monkeypatch):
    monkeypatch.setattr(momentum, "MAX_YEARS", 10)
    y = YEARS[2024]
    with pytest.raises(ValueError, match="not stationary"):
        momentum.stationary(y, y.fertility / momentum.net_reproduction(y))
