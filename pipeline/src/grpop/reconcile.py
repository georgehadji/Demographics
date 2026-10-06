"""ELSTAT's natural movement against Eurostat (Δ8c): the same definition, Greece, the
same year, compared wherever both publish a value.

Each ELSTAT step of the build runs this check, like ``indicators.check`` for a derived
indicator. A difference must be listed below with its explanation, and a listed
difference that was compared but has gone stops the build too: when Eurostat revises
its provisional year, or ELSTAT a year, someone reads the new numbers. The perinatal
mortality rate is not compared: Eurostat's counts stillbirths from another gestational
age (see ``perinatal_mortality_rate@v1``).
"""

from __future__ import annotations

import polars as pl

from grpop import indicators
from grpop.indicators import SERIES, Indicator, Series, _cells, _gind
from grpop.provenance import Nature

# INFERENCE: since 2022 Eurostat counts only residents of Greece and ELSTAT also counts
# events of residents abroad. Evidence: 2025, the one year whose release gives them
# ("Εξωτερικό", Table 2): ELSTAT minus Eurostat is +179 births and +1,016 deaths,
# residents abroad 167 births and 1,041 deaths, leaving 12 and -25. SPO03/2024's tables
# would test 2022-2024. The rates follow: other numerators and denominators.
_RESIDENTS = "EL 2022-2025"
# UNKNOWN: differences of 4 to 117 events, in both directions, in years before 2022
# (Eurostat demo_gind updated 2026-09-30, ELSTAT release of 2026-10-01).
_BIRTHS_BEFORE = "EL 1965, EL 1970, EL 1975, EL 1980, EL 1985, EL 1990, EL 2000, EL 2019"
_DEATHS_BEFORE = "EL 2000, EL 2017-2021"


def _check(definition_id: str, official: Series, decimals: int, known: str) -> Indicator:
    """``indicators.check`` compares an indicator's values with ``official``; here the
    values are ELSTAT's, so inputs and formula are unused."""
    return Indicator(
        definition_id=definition_id,
        transform_version="",
        inputs={},
        formula=lambda _: pl.DataFrame(),
        official=(official,),
        decimals=decimals,
        known_differences=_cells(known),
    )


CHECKS = {
    "live_births@v1": _check(
        "live_births@v1",
        _gind("live_births@v1", "LBIRTH"),
        0,
        f"{_BIRTHS_BEFORE}, {_RESIDENTS}",
    ),
    "deaths@v1": _check(
        "deaths@v1", _gind("deaths@v1", "DEATH"), 0, f"{_DEATHS_BEFORE}, {_RESIDENTS}"
    ),
    # births minus deaths on both sides: the years of either
    "natural_change@v1": _check(
        "natural_change@v1",
        SERIES["natural_change"],
        0,
        "EL 1965, EL 1970, EL 1975, EL 1980, EL 1985, EL 1990, EL 2000, EL 2017-2021, "
        + _RESIDENTS,
    ),
    "infant_mortality_rate@v1": _check(
        "infant_mortality_rate@v1", SERIES["infant_mortality_rate"], 1, "EL 2022-2024"
    ),
    # UNKNOWN: 2017, 0.1 apart
    "neonatal_mortality_rate@v1": _check(
        "neonatal_mortality_rate@v1",
        Series(
            "eurostat_demo_minfind",
            "neonatal_mortality_rate@v1",
            Nature.OFFICIAL_ESTIMATE,
            select={"indic_de": "NEOMORRT"},
        ),
        1,
        "EL 2017, EL 2022, EL 2024",
    ),
}


def check(definition_id: str, ours: pl.DataFrame, data: indicators.Data) -> None:
    """Raises where ELSTAT and Eurostat differ without a listed explanation, or a listed
    difference has gone."""
    unexplained, gone = indicators.check(CHECKS[definition_id], ours, data)
    if unexplained.height or gone:
        with pl.Config(tbl_rows=-1):
            raise ValueError(
                f"{definition_id}: ELSTAT and Eurostat differ where nothing explains it:\n"
                f"{unexplained}\nlisted differences that are gone: {gone}"
            )


def sources(definition_id: str) -> set[str]:
    """The Eurostat sources a definition is checked against (none if not compared)."""
    found = CHECKS.get(definition_id)
    return {s.source_id for s in found.official} if found else set()
