"""Lee-Carter mortality: the parts of the model on hand-made rates, then the gate on
Greece's rows of the WPP 2024 life tables (recorded 2026-10-15)."""

import numpy as np
import pytest
from test_indicators import data

from grpop import build, mortality
from grpop.provenance import validate_observations

AGE = np.arange(mortality.AGES)


def test_smooth_spline_keeps_a_line_and_has_the_degrees_of_freedom():
    line = 0.3 - 0.07 * AGE
    assert np.allclose(mortality.smooth_spline(line, 10), line, atol=1e-9)
    # the fitted values of noise lose most of it at few degrees of freedom
    noise = np.random.default_rng(0).normal(0, 1, mortality.AGES)
    smooth, rough = (np.std(mortality.smooth_spline(noise, df)) for df in (5, 60))
    assert smooth < 0.3 < rough


def test_basis_adds_up_to_one_everywhere():
    x = np.linspace(0, 1, 37)
    t = np.r_[[0.0] * 3, np.linspace(0, 1, 9), [1.0] * 3]
    assert np.allclose(mortality.basis(x, t, 3).sum(axis=1), 1)
    assert np.allclose(mortality.basis(x, t, 3, 2).sum(axis=1), 0, atol=1e-9)


def test_constant_rates_give_life_expectancy_one_over_the_rate():
    m = np.full(mortality.AGES, 0.02)
    assert np.allclose(mortality.expectancy(m, "female")[1:], 50)


def test_finish_repairs_negative_values_and_sums_to_one():
    bx = mortality.finish(np.array([-0.1, 0.2, -0.3, 0.4, 0.0]))
    # age 0 non-positive becomes 0; later ones half the age below
    assert np.allclose(bx, np.array([0, 0.2, 0.1, 0.4, 0.2]) / 0.9)


def test_ultimate_is_flat_to_60_and_joins_above():
    u = mortality.ultimate(np.linspace(1, 2, mortality.AGES))
    assert np.isclose(u.sum(), 1) and np.ptp(u[:61]) == 0 and np.isclose(u[61], u[60])


def test_rotation_runs_from_bx_to_the_ultimate():
    bx, u = np.full(3, 1.0), np.full(3, 3.0)
    assert (mortality.rotate(bx, u, 79) == bx).all() and (mortality.rotate(bx, u, 102) == u).all()
    assert np.allclose(mortality.rotate(bx, u, 91), 1 + 2 * np.sqrt(0.5))  # midway: weight 0.5**0.5
    assert 1 < mortality.rotate(bx, u, 85)[0] < mortality.rotate(bx, u, 95)[0] < 3


def _history() -> dict[str, tuple[list[int], np.ndarray]]:
    years = list(mortality.FIT_YEARS)
    k = np.linspace(20, -20, len(years))
    out = {}
    for sex, level in (("female", -9.5), ("male", -9.0)):
        ax = level + 0.085 * AGE + 0.5 * np.exp(-AGE)
        bx = np.full(mortality.AGES, 1 / mortality.AGES) * (1 + 0.5 * np.exp(-AGE / 30))
        out[sex] = (years, np.exp(ax[:, None] + bx[:, None] * k[None, :] / bx.sum()))
    return out


def test_projection_reaches_each_life_expectancy():
    e0 = {"female": np.array([84.0, 88.0]), "male": np.array([80.0, 85.0])}
    rates = mortality.project(_history(), e0)
    for sex, m in rates.items():
        got = [mortality.expectancy(col, sex)[0] for col in m.T]
        assert np.allclose(got, e0[sex], atol=1e-8)
    assert (rates["male"][-1] >= rates["female"][-1]).all()


FILES = {
    mortality.HISTORY["female"]: "un_wpp2024_life_table_female_grc_1950_2023.csv.gz",
    mortality.HISTORY["male"]: "un_wpp2024_life_table_male_grc_1950_2023.csv.gz",
    mortality.TARGET["female"]: "un_wpp2024_life_table_female_grc_2024_2100.csv.gz",
    mortality.TARGET["male"]: "un_wpp2024_life_table_male_grc_2024_2100.csv.gz",
}
DATA = data(mortality.SOURCES, FILES)


def test_reproduces_the_medium_variant_mortality():
    df = mortality.reproduce(DATA)
    assert df.height == 2 * 77 * mortality.AGES
    assert (df["e65_ours"] - df["e65_theirs"]).abs().max() < 0.007  # 0.0061 observed
    core = df.filter((df["age"] >= 7) & (df["age"] <= 98))
    assert ((core["ours"] / core["theirs"]) - 1).abs().max() < 0.023  # 0.0223 observed


@pytest.mark.parametrize(
    ("name", "changed"),
    [
        ("rotate", lambda bx, u, e0: bx),  # no rotation
        ("smooth_spline", lambda y, df: y),  # a(x) not smoothed
        ("FIT_YEARS", range(1990, 2024)),  # b(x) fitted on 1990-2023
    ],
)
def test_another_model_is_not_the_variant(monkeypatch, name, changed):
    monkeypatch.setattr(mortality, name, changed)
    with pytest.raises(ValueError, match="not reproduced"):
        mortality.reproduce(DATA)


def test_the_step_publishes_the_variants_life_expectancy():
    df = validate_observations(build._mortality(DATA))
    assert df.height == 77 * 2 * 2
    assert set(df["nature"]) == {"projected"} and set(df["age"]) == {"0", "65"}
    by = {(s, a, p): v for s, a, p, v in df.select("sex", "age", "period", "value").iter_rows()}
    assert by["female", "0", "2024"] == 84.4562  # WPP 2024 medium variant, Greece


# Ours, from Greece's Eurostat life tables, 1961-2024 (recorded 2026-10-16)
OURS = data(
    mortality.OURS_SOURCES, {mortality.EUROSTAT: "eurostat_demo_mlifetable_el_1961_2024.json"}
)


def test_a_zero_rate_takes_the_years_beside_it():
    m = mortality._fill(np.array([[1e-4, 0.0, 3e-4], [0.0, 2e-3, 2e-3]]))
    assert np.allclose(m, [[1e-4, 2e-4, 3e-4], [2e-3, 2e-3, 2e-3]])


def test_our_life_table_gives_eurostats_life_expectancy():
    years, rates, lifexp, provisional = mortality.eurostat_rates(OURS)
    assert (years[0], years[-1], rates["female"].shape) == (1961, 2024, (86, 64))
    assert not provisional
    mortality.check_life_tables(years, rates, lifexp)
    rates["male"][60, years.index(1990)] *= 1.5  # one rate off: e0 moves 0.1 years
    with pytest.raises(ValueError, match="not reproduced: male 1990 e0"):
        mortality.check_life_tables(years, rates, lifexp)


def test_the_drift_scenario_and_its_backtest():
    df = validate_observations(build.STEPS["life_expectancy_scenario_lc"].run(OURS))
    assert set(df["nature"]) == {"scenario"}
    assert df.group_by("scenario_id").len().sort("scenario_id").rows() == [
        (mortality.SCENARIO, 76 * 2 * 2 * 5),  # 2025-2100, sexes, ages 0 and 65, five values
        (mortality.BACKTEST, 10 * 2 * 2 * 5),  # 2010-2019
    ]
    v = {
        (s, i, a, p, b): x
        for s, a, p, b, x, i in df.select(
            "sex", "age", "period", "interval", "value", "scenario_id"
        ).iter_rows()
    }
    scenario, backtest = mortality.SCENARIO, mortality.BACKTEST
    assert round(v["female", scenario, "0", "2100", None], 1) == 92.6
    assert round(v["male", scenario, "0", "2100", None], 1) == 89.5
    for key in [k for k in v if k[4] is None]:
        bounds = [v[(*key[:4], b)] for b in ("95_lower", "80_lower", None, "80_upper", "95_upper")]
        assert bounds == sorted(bounds)
    years, rates, _, _ = mortality.eurostat_rates(OURS)
    inside = 0
    for sex, m in rates.items():
        for t in range(2010, 2020):
            e = mortality.expectancy(m[:, years.index(t)], sex, mortality.EUROSTAT_A0)
            for age in (0, 65):
                key = (sex, backtest, str(age), str(t))
                assert abs(v[(*key, None)] - e[age]) < 0.66  # 0.652 observed
                inside += v[(*key, "95_lower")] <= e[age] <= v[(*key, "95_upper")]
    assert inside == 39  # of 40
