"""Lee-Carter mortality: the parts of the model on hand-made rates (not data)."""

import numpy as np

from grpop import mortality

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
