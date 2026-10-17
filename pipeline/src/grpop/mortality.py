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
  solve it by 60 bisections; MortCast stops within 0.01 years, which moves e65 by up
  to 0.012 years against 0.006 when solved exactly.
- Men's rate at the open age is at least women's while women live longer.
- Life table: single ages, a(0) by the Andreev-Kingkade rule, a(x) = 0.5 above, the
  open age L = l / m; it reproduces the UN's e0 of every year.

The gate compares, every year and both sexes, life expectancy at 65 within
``E65_TOLERANCE`` and the death rates at ages 7-98 within ``RATE_TOLERANCE``; the
youngest and oldest ages, where the UN's smoothing of a(x) differs from R's (cause
UNKNOWN), within ``EDGE_TOLERANCE``. e0 is matched by construction and not a test.
VERIFIED 2026-10-15 on Greece, 2024-2100: e65 at most 0.0061 years off (women) and
0.0017 (men); rates at ages 7-98 at most 2.2% and 1.9% (95% of cells within 1.3% and
0.9%), at the other ages 9.6%; median 0.4% and 0.2%. The gate refuses each of: no rotation (e65
0.11 years off), a(x) not smoothed (0.014 years, rates 6.5%), b(x) fitted from 1990
(0.77 years), women's b(x) for both sexes (0.25 years).

Then ours (``ours``, decided by the responsible editor 2026-10-16): the same b(x),
``finish``, ``ultimate`` and ``rotate`` on Greece's Eurostat life tables, 1961 to the
latest year, ages 0-84 and 85+ (85+ as l(85)/T(85); single ages to 84 and 85+ in
1961-2013, to 94 and 95+ since 2014, VERIFIED 2026-10-16). A rate of zero, at a young
age in a few years, is the mean of the years beside it. First our life table on
Eurostat's rates must give Eurostat's LIFEXP at 0 and 65 (a(0) = 0.2, Eurostat's own):
VERIFIED 2026-10-16, every year and sex within 0.0506 years (median 0.023), against
``LIFE_TABLE_TOLERANCE``. k(t) is refitted each year to the year's e0 and taken as a
random walk; its drift, the mean of both sexes', runs from 1961 to 2019, so the
2020-2022 deaths do not set it; the projection starts from the latest year's observed
rates. A scenario (ADR 0008): the consequence of the trend continuing, not a forecast.
Backtest, the same model from 2009 over 2010-2019 (published as ``BACKTEST``), VERIFIED
2026-10-16: e0 at most 0.41 years off (women) and 0.65 (men), e65 0.38 and 0.65; 33 of
40 values inside the 80% interval, 39 inside the 95%. In 2100 ours gives women 92.6 years
at birth and men 89.5, WPP 2024 93.4 and 89.6. ponytail: no Kannisto above 85 here; the
cohort engine, which needs ages to 100+, takes it from ``cokannisto`` below.

Kannisto (MortCast's ``cokannisto``, ported: logit m(x) = log c + d x, one slope for
both sexes, a level each, least squares) for ages above the last one fitted, the open
age as l / T of its table closed at 130. Its gate (``reproduce_kannisto``, in the WPP
step): fitted on WPP 2024's projected rates at 80-94, it gives the UN's 95-99 and 100+,
2024-2100, within ``KANNISTO_TOLERANCE``. The UN's own old-age rates come from its
Lee-Carter (reproduced above), so this checks that Kannisto follows a published old-age
pattern, not that it reproduces a published Kannisto (INFERENCE: none for Greece is
public without registration). VERIFIED 2026-10-17: at most 5.0% off (women, 95-99;
median 2.4%), 100+ within 4.8%. The gate refuses Gompertz (75%) and a fit from 70
(19%). On Eurostat's Greek rates the fit from 80-84 put men's 85-94 6-24% too high
(2022-2024): the cohort engine must fit where the data allow, which it decides.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import polars as pl

from grpop.definitions import get_definition
from grpop.indicators import Data
from grpop.parse import eurostat
from grpop.parse.un_wpp_csv import LIFE_EXPECTANCY_ID, greece
from grpop.provenance import Interval, Nature, Status
from grpop.sources.registry import get_source

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
BISECTIONS = 60  # an interval of width 60 to 1e-16
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


def expectancy(mx: np.ndarray, sex: str, a0: float | None = None) -> np.ndarray:
    """Life expectancy at each age of a single-age life table with an open last age;
    a(0) by the Andreev-Kingkade rule unless given."""
    (b1, c1, s1), (b2, c2, s2), c3 = A0[sex]
    m0 = mx[0]
    a = np.full(len(mx) - 1, 0.5)
    a[0] = c1 + s1 * m0 if m0 < b1 else (c2 + s2 * m0 if m0 < b2 else c3)
    if a0 is not None:
        a[0] = a0
    q = mx[:-1] / (1 + (1 - a) * mx[:-1])
    lx = np.concatenate(([1.0], np.cumprod(1 - q)))
    lived = np.concatenate((lx[1:] + a * (lx[:-1] - lx[1:]), [lx[-1] / mx[-1]]))
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


# --- Kannisto above the last fitted age, for the cohort engine (ages to 100+) ---

KANNISTO_FIT = np.arange(80.0, 95.0)  # the gate's ages, the UN's 80-94
KANNISTO_TOP = 130  # the table above the open age closes here, as MortCast projects to
KANNISTO_TOLERANCE = 0.055  # relative, ages 95-99 and 100+


def cokannisto(female: np.ndarray, male: np.ndarray, ages: np.ndarray) -> dict[str, np.ndarray]:
    """MortCast's ``cokannisto.estimate``: logit m(x) = log c + d x by least squares on
    both sexes' rates at ``ages``, one slope d, a level c each; (log c, d) by sex."""
    y = np.log(np.r_[male, female] / (1 - np.r_[male, female]))
    n = len(ages)
    x = np.column_stack([np.ones(2 * n), np.r_[np.ones(n), np.zeros(n)], np.r_[ages, ages]])
    level, men, slope = np.linalg.lstsq(x, y, rcond=None)[0]
    return {"female": np.array([level, slope]), "male": np.array([level + men, slope])}


def kannisto(pars: np.ndarray, ages: np.ndarray) -> np.ndarray:
    """MortCast's ``kannisto.predict``: c e^(d x) / (1 + c e^(d x))."""
    z = np.exp(pars[0] + pars[1] * ages)
    return np.asarray(z / (1 + z))


def kannisto_open(pars: np.ndarray, start: int) -> float:
    """The rate of the open age ``start``+, l / T of the Kannisto table to KANNISTO_TOP."""
    m = kannisto(pars, np.arange(start, KANNISTO_TOP + 1.0))
    lx = np.r_[1.0, np.cumprod((1 - m / 2) / (1 + m / 2))]
    return float(1 / ((lx[1:] + lx[:-1]) / 2).sum())


def reproduce_kannisto(data: Data) -> pl.DataFrame:
    """WPP 2024's projected death rates of Greece at 95-99 and 100+ by Kannisto from its
    rates at 80-94, each year and sex: sex, year, age, ours, theirs. Raises if any is
    more than ``KANNISTO_TOLERANCE`` off."""
    tables = {sex: _table(data[TARGET[sex]][1]) for sex in TARGET}
    years = tables["female"][0]
    rows, off = [], []
    for j, year in enumerate(years):
        fit = KANNISTO_FIT.astype(int)
        pars = cokannisto(tables["female"][1][fit, j], tables["male"][1][fit, j], KANNISTO_FIT)
        for sex, p in pars.items():
            ours = np.r_[kannisto(p, np.arange(95.0, AGES - 1)), kannisto_open(p, AGES - 1)]
            theirs = tables[sex][1][95:, j]
            if (np.abs(ours / theirs - 1) > KANNISTO_TOLERANCE).any():
                off.append(f"{sex} {year}")
            rows += [
                (sex, year, 95 + i, o, t) for i, (o, t) in enumerate(zip(ours, theirs, strict=True))
            ]
    if off:
        raise ValueError(f"WPP 2024 old-age mortality not reproduced: {', '.join(off[:5])}")
    return pl.DataFrame(rows, schema=["sex", "year", "age", "ours", "theirs"], orient="row")


# --- ours: Lee-Carter with drift from Eurostat's life tables (Δ9, decided 2026-10-16) ---

EUROSTAT = "eurostat_demo_mlifetable"
OURS_SOURCES = frozenset({EUROSTAT})
GEO = "EL"
OPEN_AGE = 85  # ages 0-84 and 85+, which every Greek table since 1961 has
EUROSTAT_A0 = 0.2  # Eurostat's a(0), (T(0) - T(1) - l(1)) / (l(0) - l(1)), every year
LIFE_TABLE_TOLERANCE = 0.06  # years: LIFEXP is rounded to 0.1, the rates to 5 decimals
DRIFT_END = 2019  # the drift ends before 2020-2022
BACKTEST_JUMP_OFF, BACKTEST_END = 2009, 2019
HORIZON = 2100
LEVELS = {  # normal quantiles of the two-sided 80% and 95% intervals
    1.2815515655446004: (Interval.LOWER_80, Interval.UPPER_80),
    1.959963984540054: (Interval.LOWER_95, Interval.UPPER_95),
}
SCENARIO = "kohortes_lc_drift"
BACKTEST = "kohortes_lc_drift_from_2009"
OURS_TRANSFORM = "lee_carter_drift@0.1"
_CODES = {"female": "F", "male": "M"}


def _fill(m: np.ndarray) -> np.ndarray:
    """Death rates (age x year) with each zero (no death at one young age that year) as
    the mean of the same age in the years beside it."""
    m = m.copy()
    for x, t in np.argwhere(m <= 0):
        near = [m[x, j] for j in (t - 1, t + 1) if 0 <= j < m.shape[1] and m[x, j] > 0]
        if not near:
            raise ValueError(f"{EUROSTAT}: no death rate beside age {x}, year index {t}")
        m[x, t] = np.mean(near)
    return m


def eurostat_rates(
    data: Data,
) -> tuple[list[int], dict[str, np.ndarray], dict[tuple[str, int, int], float], bool]:
    """Greece's years, death rates by sex (ages 0-84 and 85+ x year; 85+ as l(85)/T(85)),
    Eurostat's LIFEXP at 0 and 65 by (sex, age, year), and whether a value is provisional."""
    df = eurostat._parsed(data[EUROSTAT][1])[1].filter(
        pl.col("geo") == GEO,
        pl.col("sex").is_in(list(_CODES.values())),
        pl.col("value").is_not_null(),
    )
    cells = {
        (i, s, a, int(t)): v
        for i, s, a, t, v in df.select("indic_de", "sex", "age", "time", "value").iter_rows()
    }
    years = sorted({k[3] for k in cells if k[0] == "DEATHRATE"})
    rates, lifexp = {}, {}
    for sex, s in _CODES.items():
        columns = []
        for t in years:
            top = "Y85" if ("SURVIVORS", s, "Y85", t) in cells else "Y_GE85"
            try:
                m = [cells["DEATHRATE", s, "Y_LT1", t]]
                m += [cells["DEATHRATE", s, f"Y{x}", t] for x in range(1, OPEN_AGE)]
                m.append(cells["SURVIVORS", s, top, t] / cells["TOTPYLIVED", s, top, t])
                for x, code in ((0, "Y_LT1"), (65, "Y65")):
                    lifexp[sex, x, t] = cells["LIFEXP", s, code, t]
            except KeyError as e:
                raise ValueError(f"{EUROSTAT}: {sex} {t} lacks {e}") from None
            columns.append(m)
        rates[sex] = _fill(np.array(columns).T)
    provisional = any(eurostat.flag_meaning(f)[0] for f in df["flag"].drop_nulls().unique())
    return years, rates, lifexp, provisional


def check_life_tables(
    years: list[int], rates: dict[str, np.ndarray], lifexp: dict[tuple[str, int, int], float]
) -> None:
    """Our life table on Eurostat's rates gives Eurostat's LIFEXP at 0 and 65, every year
    and sex, within ``LIFE_TABLE_TOLERANCE``; raises otherwise."""
    off = []
    for sex, m in rates.items():
        for j, t in enumerate(years):
            e = expectancy(m[:, j], sex, EUROSTAT_A0)
            off += [
                f"{sex} {t} e{x}"
                for x in (0, 65)
                if abs(e[x] - lifexp[sex, x, t]) > LIFE_TABLE_TOLERANCE
            ]
    if off:
        raise ValueError(f"Eurostat's life expectancy not reproduced: {', '.join(off[:5])}")


def _k(ax: np.ndarray, bx: np.ndarray, e0: float, sex: str) -> float:
    """The k at which exp(a + b k) gives life expectancy ``e0``."""
    low, high = -1000.0, 1000.0
    for _ in range(80):
        k = (low + high) / 2
        longer = expectancy(np.exp(ax + bx * k), sex, EUROSTAT_A0)[0] > e0
        low, high = (k, high) if longer else (low, k)
    return (low + high) / 2


def drift(
    years: list[int], rates: dict[str, np.ndarray], jump_off: int, drift_end: int, end: int
) -> dict[tuple[str, str | None], np.ndarray]:
    """Life expectancy at 0 and 65 (year x 2) of each year after ``jump_off`` to ``end``,
    by (sex, interval bound or None), from the rates of the years up to ``jump_off``.

    b(x): fitted by sex on those years around their mean log rate, repaired as
    ``finish`` does, the sexes' mean; rotated as in WPP by the mean e0 of the year
    before. k(t): refitted each year to the year's e0 from the jump-off rates; a random
    walk with one drift for both sexes, the mean of the two from the first year to
    ``drift_end``; each sex's own variance, the drift's uncertainty added.
    """
    j = years.index(jump_off)
    logs = {sex: np.log(m[:, : j + 1]) for sex, m in rates.items()}
    bs = []
    for log in logs.values():
        centred = log - log.mean(axis=1, keepdims=True)
        total = centred.sum(axis=0)
        bs.append(finish(centred @ total / (total @ total)))
    bx = np.mean(bs, axis=0)
    u = ultimate(bx)
    ax = {sex: log[:, j] for sex, log in logs.items()}
    e0 = {
        sex: [expectancy(m[:, i], sex, EUROSTAT_A0)[0] for i in range(j + 1)]
        for sex, m in rates.items()
    }
    n = years.index(drift_end)
    kt = {sex: np.array([_k(ax[sex], bx, e, sex) for e in e0[sex][: n + 1]]) for sex in rates}
    own = {sex: (k[-1] - k[0]) / n for sex, k in kt.items()}
    d = np.mean(list(own.values()))
    sigma = {sex: np.std(np.diff(k) - own[sex], ddof=1) for sex, k in kt.items()}
    # a lower bound of life expectancy is an upper bound of k
    bounds: list[tuple[str | None, float]] = [(None, 0.0)]
    bounds += [(lower.value, z) for z, (lower, _) in LEVELS.items()]
    bounds += [(upper.value, -z) for z, (_, upper) in LEVELS.items()]
    out: dict[tuple[str, str | None], list[np.ndarray]] = {
        (sex, b): [] for sex in rates for b, _ in bounds
    }
    previous = np.mean([e[-1] for e in e0.values()])
    for h in range(1, end - jump_off + 1):
        b = rotate(bx, u, previous)
        for sex in rates:
            for bound, z in bounds:
                k = d * h + z * sigma[sex] * np.sqrt(h + h * h / n)
                out[sex, bound].append(
                    expectancy(np.exp(ax[sex] + b * k), sex, EUROSTAT_A0)[[0, 65]]
                )
        previous = np.mean([out[sex, None][-1][0] for sex in rates])
    return {key: np.array(v) for key, v in out.items()}


def _scenario(
    data: Data,
    frames: dict[str, tuple[int, dict[tuple[str, str | None], np.ndarray]]],
    provisional: bool,
) -> pl.DataFrame:
    snapshot, raw = data[EUROSTAT]
    definition, source = get_definition(LIFE_EXPECTANCY_ID), get_source(EUROSTAT)
    rows = [
        (scenario, str(jump_off + 1 + i), sex, str(age), bound, float(v[i, a]))
        for scenario, (jump_off, values) in frames.items()
        for (sex, bound), v in values.items()
        for i in range(len(v))
        for a, age in enumerate((0, 65))
    ]
    schema = ["scenario_id", "period", "sex", "age", "interval", "value"]
    df = pl.DataFrame(
        rows, schema={c: pl.Float64 if c == "value" else pl.String for c in schema}, orient="row"
    )
    return df.select(
        metric=pl.lit(definition.metric),
        definition_id=pl.lit(definition.id),
        geo_code=pl.lit(GEO),
        geo_vintage=pl.lit("NUTS2024"),
        period="period",
        sex="sex",
        age="age",
        value="value",
        unit=pl.lit(definition.unit),
        source=pl.lit(source.provider),
        dataset_code=pl.lit(source.dataset_code),
        source_url=pl.lit(snapshot.source_url),
        vintage=pl.lit(eurostat._parsed(raw)[0]["updated"]),
        retrieved_at=pl.lit(snapshot.retrieved_at, dtype=pl.Datetime("us", "UTC")),
        transform_version=pl.lit(OURS_TRANSFORM),
        nature=pl.lit(Nature.SCENARIO.value),
        status=pl.lit(Status.PROVISIONAL.value if provisional else Status.FINAL.value),
        break_in_series=pl.lit(False),
        scenario_id="scenario_id",
        interval="interval",
    ).sort("scenario_id", "period", "sex", "age", "interval", nulls_last=False)


def ours(data: Data) -> pl.DataFrame:
    """Greece's life expectancy at 0 and 65 by sex if mortality keeps its trend since
    1961 (``SCENARIO``, from the latest year to ``HORIZON``), and the same model from
    2009 over 2010-2019 (``BACKTEST``), once our life table reproduces Eurostat's."""
    years, rates, lifexp, provisional = eurostat_rates(data)
    check_life_tables(years, rates, lifexp)
    frames = {
        SCENARIO: (years[-1], drift(years, rates, years[-1], DRIFT_END, HORIZON)),
        BACKTEST: (
            BACKTEST_JUMP_OFF,
            drift(years, rates, BACKTEST_JUMP_OFF, BACKTEST_JUMP_OFF, BACKTEST_END),
        ),
    }
    return _scenario(data, frames, provisional)
