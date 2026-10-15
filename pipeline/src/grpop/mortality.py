"""Lee-Carter mortality, and first its gate: WPP 2024's medium-variant death rates for
Greece, 2024-2100, reproduced from the UN's own inputs (CLAUDE.md: every model
reproduces a published result first).

The UN's method (WPP 2024 Methodology Report, printed p. 46, footnote 72; VERIFIED):
Greece is among the countries projected by the coherent rotated Lee-Carter model,
constrained to the projected life expectancy at birth of each sex. The implementation is
MortCast (R package; ``leecarter.estimate``, ``lileecarter.estimate``,
``rotate.leecarter``, ``ultimate.bx`` in ``R/LC.R``, the solve in ``src/functions.c``),
ported here:

- a(x): the mean log death rate of 2015-2019, smoothed over age by a cubic smoothing
  spline with df = ceil(ages / 2) (R ``smooth.spline``), age 0 kept as it is.
- b(x): fitted by sex on 1950-2023 (k(t) = sum of log rates - sum a(x)), negative values
  repaired as ``.finish.bx`` does, scaled to sum 1; both sexes share their mean.
- Rotation: b(x) moves towards the ultimate b(x) (ages 0-60 at the mean of 15-60, older
  ages scaled so b(61) = b(60)) as the mean of both sexes' e0 goes from 80 to 102.
- k(t): the value at which the life table gives the UN's e0 of that sex and year. We
  solve it by 100 bisections; MortCast stops within 0.01 years, which moves e65 by up
  to 0.012 years against 0.006 when solved exactly.
- Men's rate at the open age is at least women's while women live longer.
- Life table: single ages, a(0) by the Andreev-Kingkade rule, a(x) = 0.5 above, the
  open age L = l / m; it reproduces the UN's e0 of every year.

The gate compares, every year and both sexes, life expectancy at 65 within
``E65_TOLERANCE`` and the death rates at ages 7-98 within ``RATE_TOLERANCE``; the
youngest and oldest ages, where the UN's smoothing of a(x) differs from R's (cause
UNKNOWN), within ``EDGE_TOLERANCE``. e0 is matched by construction and not a test.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import polars as pl

from grpop.indicators import Data
from grpop.parse.un_wpp_csv import greece

HISTORY = {
    "female": "un_wpp_2024_life_table_female_1950_2023",
    "male": "un_wpp_2024_life_table_male_1950_2023",
}
TARGET = {
    "female": "un_wpp_2024_life_table_female_2024_2100",
    "male": "un_wpp_2024_life_table_male_2024_2100",
}
SOURCES = frozenset({*HISTORY.values(), *TARGET.values()})
AGES = 101  # 0-99 and 100+
FIT_YEARS = range(1950, 2024)
AX_YEARS = range(2015, 2020)
E0_LOW, E0_HIGH, ROTATION_POWER = 80.0, 102.0, 0.5
BISECTIONS = 100
E65_TOLERANCE = 0.01  # years
RATE_TOLERANCE = 0.025  # relative, ages 7-98
EDGE_TOLERANCE = 0.12  # relative, ages 0-6 and 99-100
CORE = slice(7, 99)
# Andreev-Kingkade a(0): (below m0, a + b m0), then (below m0, a + b m0), else a
A0 = {
    "female": ((0.01724, 0.14903, -2.05527), (0.06891, 0.04667, 3.88089), 0.31411),
    "male": ((0.0230, 0.14929, -1.99545), (0.08307, 0.02832, 3.26021), 0.29915),
}


# --- R's smooth.spline: cubic B-splines on R's knots, df matched by the trace ---


def nknots(n: int) -> int:
    """R's ``.nknots.smspl``: how many knots ``smooth.spline`` puts on n points."""
    if n < 50:
        return n
    a1, a2, a3, a4 = np.log2([50, 100, 140, 200])
    if n < 200:
        return int(2 ** (a1 + (a2 - a1) * (n - 50) / 150))
    if n < 800:
        return int(2 ** (a2 + (a3 - a2) * (n - 200) / 600))
    if n < 3200:
        return int(2 ** (a3 + (a4 - a3) * (n - 800) / 2400))
    return int(200 + (n - 3200) ** 0.2)


def _divide(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.asarray(np.divide(a, b, out=np.zeros_like(a), where=b != 0))


def basis(x: np.ndarray, t: np.ndarray, k: int, derivative: int = 0) -> np.ndarray:
    """B-splines of degree ``k`` on knots ``t`` at ``x`` (Cox-de Boor), or their
    ``derivative``; one column per spline. The last knot belongs to the last interval."""
    if derivative:
        lower = basis(x, t, k - 1, derivative - 1)
        i = np.arange(len(t) - k - 1)
        left = _divide(lower[:, i], t[i + k] - t[i])
        return np.asarray(k * (left - _divide(lower[:, i + 1], t[i + k + 1] - t[i + 1])))
    b = ((t[:-1] <= x[:, None]) & (x[:, None] < t[1:])).astype(float)
    b[x == t[-1], np.flatnonzero(t[:-1] < t[1:])[-1]] = 1.0
    for d in range(1, k + 1):
        i = np.arange(len(t) - d - 1)
        b = _divide((x[:, None] - t[i]) * b[:, i], t[i + d] - t[i]) + _divide(
            (t[i + d + 1] - x[:, None]) * b[:, i + 1], t[i + d + 1] - t[i + 1]
        )
    return b


def smooth_spline(y: np.ndarray, df: float) -> np.ndarray:
    """R's ``smooth.spline(y, df = df)$y`` for equally spaced points: the penalised cubic
    spline whose smoother matrix has trace ``df``."""
    n = len(y)
    x = np.linspace(0.0, 1.0, n)
    inner = x[np.floor(np.linspace(1, n, nknots(n))).astype(int) - 1]
    t = np.r_[[inner[0]] * 3, inner, [inner[-1]] * 3]
    design = basis(x, t, 3)
    # roughness: the integral of products of second derivatives, linear on each interval
    nodes, weights = np.polynomial.legendre.leggauss(2)
    penalty = np.zeros((design.shape[1],) * 2)
    for a, b in pairwise(inner):
        second = basis((b - a) / 2 * nodes + (a + b) / 2, t, 3, 2)
        penalty += second.T @ (second * ((b - a) / 2 * weights)[:, None])
    gram = design.T @ design

    def trace(log_lambda: float) -> float:
        return float(np.trace(np.linalg.solve(gram + np.exp(log_lambda) * penalty, gram)))

    low, high = -40.0, 20.0  # the trace falls as lambda grows
    for _ in range(BISECTIONS):
        mid = (low + high) / 2
        low, high = (mid, high) if trace(mid) > df else (low, mid)
    smoother = gram + np.exp((low + high) / 2) * penalty
    return np.asarray(design @ np.linalg.solve(smoother, design.T @ y))


# --- life table and the coherent rotated Lee-Carter model ---


def expectancy(mx: np.ndarray, sex: str) -> np.ndarray:
    """Life expectancy at each age of a single-age life table with an open last age."""
    (b1, c1, s1), (b2, c2, s2), c3 = A0[sex]
    m0 = mx[0]
    a = np.full(AGES - 1, 0.5)
    a[0] = c1 + s1 * m0 if m0 < b1 else (c2 + s2 * m0 if m0 < b2 else c3)
    q = mx[:-1] / (1 + (1 - a) * mx[:-1])
    lx = np.r_[1.0, np.cumprod(1 - q)]
    lived = np.r_[lx[1:] + a * (lx[:-1] - lx[1:]), lx[-1] / mx[-1]]
    return np.asarray(np.cumsum(lived[::-1])[::-1] / lx)


def finish(bx: np.ndarray) -> np.ndarray:
    """MortCast's ``.finish.bx``: non-positive values from half the age below, zeros
    from the age below, scaled to sum 1."""
    bx = bx.copy()
    negative = np.flatnonzero(bx <= 0)
    if len(negative) and negative[0] == 0:
        bx[0], negative = 0.0, negative[1:]
    while len(negative):
        bx[negative] = 0.5 * bx[negative - 1]
        negative = np.flatnonzero(bx < 0)
    for i in range(len(bx) - 1, 0, -1):
        if bx[i] == 0:
            bx[i] = bx[i - 1]
    return np.asarray(bx / bx.sum())


def ultimate(bx: np.ndarray) -> np.ndarray:
    """The ultimate b(x): ages 0-60 at the mean of 15-60, older ages scaled to join."""
    u = bx.copy()
    u[:61] = bx[15:61].mean()
    u[61:] *= u[60] / u[61]
    return np.asarray(u / u.sum())


def rotate(bx: np.ndarray, ultimate_bx: np.ndarray, e0: float) -> np.ndarray:
    """b(x) rotated towards the ultimate one at the mean e0 of both sexes."""
    if e0 < E0_LOW:
        return bx
    if e0 >= E0_HIGH:
        return ultimate_bx
    w = (e0 - E0_LOW) / (E0_HIGH - E0_LOW)
    weight = (0.5 * (1 + np.sin(np.pi / 2 * (2 * w - 1)))) ** ROTATION_POWER
    return np.asarray((1 - weight) * bx + weight * ultimate_bx)


def solve(ax: np.ndarray, bx: np.ndarray, e0: float, sex: str, floor: float = 0.0) -> np.ndarray:
    """Death rates exp(a + b k) with the k that gives life expectancy ``e0``, between
    MortCast's bounds; the open age at least ``floor``."""
    positive = bx[bx > 0]
    high = (0 - ax.max()) / positive.max()
    low = (np.floor(min(-12, ax.min() - 0.1)) - ax.min()) / positive.min()

    def rates(k: float) -> np.ndarray:
        m = np.exp(ax + bx * k)
        m[-1] = max(m[-1], floor)
        return m

    for _ in range(BISECTIONS):
        k = (low + high) / 2
        low, high = (k, high) if expectancy(rates(k), sex)[0] > e0 else (low, k)
    return rates((low + high) / 2)


def fit(log_rates: np.ndarray, years: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """a(x) and b(x) of one sex from log death rates (age x year) of ``years``."""
    ax = log_rates[:, [years.index(y) for y in AX_YEARS]].mean(axis=1)
    ax[1:] = smooth_spline(ax, np.ceil(len(ax) / 2))[1:]
    fitted = log_rates[:, [years.index(y) for y in FIT_YEARS]]
    kt = fitted.sum(axis=0) - ax.sum()
    return ax, finish((fitted - ax[:, None]) @ kt / (kt @ kt))


def project(
    history: dict[str, tuple[list[int], np.ndarray]], e0: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    """Death rates (age x year) of both sexes that reach each year's ``e0``, from the
    rates of past years (years, age x year)."""
    pars = {sex: fit(np.log(rates), years) for sex, (years, rates) in history.items()}
    bx = (pars["female"][1] + pars["male"][1]) / 2
    u = ultimate(bx)
    out: dict[str, list[np.ndarray]] = {"female": [], "male": []}
    for female, male in zip(e0["female"], e0["male"], strict=True):
        b = rotate(bx, u, (female + male) / 2)
        f = solve(pars["female"][0], b, female, "female")
        out["female"].append(f)
        out["male"].append(solve(pars["male"][0], b, male, "male", f[-1] if female > male else 0))
    return {sex: np.column_stack(m) for sex, m in out.items()}


# --- the gate ---


def _table(raw: bytes) -> tuple[list[int], np.ndarray, np.ndarray]:
    """Years, death rates (age x year) and life expectancy (age x year) of a WPP file."""
    df = (
        greece(raw, ["Time", "AgeGrpStart", "mx", "ex"])
        .select(
            pl.col("Time").cast(pl.Int32),
            pl.col("AgeGrpStart").cast(pl.Int32),
            pl.col("mx").cast(pl.Float64),
            pl.col("ex").cast(pl.Float64),
        )
        .sort("Time", "AgeGrpStart")
    )
    years = df["Time"].unique(maintain_order=True).to_list()
    if df["AgeGrpStart"].to_list() != list(range(AGES)) * len(years):
        raise ValueError(f"expected ages 0-{AGES - 1} in each of {len(years)} years")
    shape = (len(years), AGES)
    return years, df["mx"].to_numpy().reshape(shape).T, df["ex"].to_numpy().reshape(shape).T


def reproduce(data: Data) -> pl.DataFrame:
    """WPP 2024's projected death rates of Greece by our Lee-Carter from the UN's past
    rates and e0: sex, year, age, ours, theirs (rates), and e65 of both. Raises if
    any year is outside the tolerances."""
    history, target = {}, {}
    for sex in HISTORY:
        years, mx, _ = _table(data[HISTORY[sex]][1])
        history[sex] = (years, mx)
        target[sex] = _table(data[TARGET[sex]][1])
    ours = project(history, {sex: ex[0] for sex, (_, _, ex) in target.items()})
    frames, off = [], []
    for sex, (years, mx, ex) in target.items():
        relative = np.abs(ours[sex] / mx - 1)
        e65 = np.array([expectancy(m, sex)[65] for m in ours[sex].T])
        core = relative[CORE].max(axis=0)
        edge = np.r_[relative[: CORE.start], relative[CORE.stop :]].max(axis=0)
        bad = np.abs(e65 - ex[65]) > E65_TOLERANCE
        bad |= (core > RATE_TOLERANCE) | (edge > EDGE_TOLERANCE)
        off += [f"{sex} {y}" for y, b in zip(years, bad, strict=True) if b]
        frames.append(
            pl.DataFrame(
                {
                    "sex": sex,
                    "year": np.repeat(years, AGES),
                    "age": np.tile(np.arange(AGES), len(years)),
                    "ours": ours[sex].T.ravel(),
                    "theirs": mx.T.ravel(),
                    "e65_ours": np.repeat(e65, AGES),
                    "e65_theirs": np.repeat(ex[65], AGES),
                }
            )
        )
    if off:
        raise ValueError(f"WPP 2024 mortality not reproduced: {', '.join(off[:5])}")
    return pl.concat(frames)
