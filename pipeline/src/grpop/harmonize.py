"""Greek NUTS codes (ADR 0005, layer L3).

Greek NUTS codes and boundaries are the same in NUTS 2013, 2016, 2021 and 2024:
Eurostat's correspondence tables list only one Greek name change (EL421, 2021).
Eurostat also publishes Greek regional series back-cast to these codes (EL51 from
1991 in demo_r_pjanaggr3). So no code mapping is needed. What remains is to reject
codes of older versions (NUTS 2010, e.g. EL11 -> EL51, EL300 split into EL301-EL307)
and to check that each level adds up to its parent.

The reference list data/reference/nuts2024_el.csv is the Greek part of GISCO's
NUTS_AT_2024.csv (registry: gisco_nuts_2024).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from grpop.provenance import OBSERVATION_KEY

REFERENCE = Path(__file__).resolve().parents[3] / "data" / "reference"


def greek_nuts() -> set[str]:
    """The 70 Greek NUTS 2024 codes, country (EL) to NUTS 3."""
    return set(pl.read_csv(REFERENCE / "nuts2024_el.csv")["geo_code"])


def check_greek_codes(obs: pl.DataFrame) -> None:
    """Raise if a Greek geo_code is not a current NUTS code (e.g. a NUTS 2010 code)."""
    el = set(obs.filter(pl.col("geo_code").str.starts_with("EL"))["geo_code"])
    unknown = el - greek_nuts()
    if unknown:
        raise ValueError(f"Greek codes outside NUTS 2024: {sorted(unknown)}")


def hierarchy_gaps(obs: pl.DataFrame, *, tolerance: float = 0.5) -> pl.DataFrame:
    """Greek parents whose value differs from the sum of their children.

    Compares every Greek code with the sum of the codes one level below it (a child's
    parent is its code without the last character), per observation key without
    geography. Status and nature are not part of the match, so a provisional child
    still counts towards a final parent. Returns the offending rows; an empty frame
    means every level adds up.
    """
    keys = [k for k in OBSERVATION_KEY if k not in ("geo_code", "geo_vintage", "scenario_id")]
    el = obs.filter(pl.col("geo_code").str.starts_with("EL") & pl.col("value").is_not_null())
    children = (
        el.filter(pl.col("geo_code").str.len_chars() > 2)
        .group_by([*keys, pl.col("geo_code").str.head(-1)])
        .agg(children=pl.col("value").sum())
    )
    return (
        el.join(children, on=[*keys, "geo_code"], how="inner")
        .filter((pl.col("value") - pl.col("children")).abs() > tolerance)
        .select("geo_code", *keys, "value", "children")
    )
