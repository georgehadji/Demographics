"""Greek NUTS codes (ADR 0005, layer L3).

Greek NUTS codes and boundaries are the same in NUTS 2013, 2016, 2021 and 2024:
Eurostat's correspondence tables list only one Greek name change (EL421, 2021).
Eurostat also publishes Greek regional series back-cast to these codes (EL51 from
1991 in demo_r_pjanaggr3), except the census year 2011 for EL5, EL6 and their
regions, which some tables give only in NUTS 2010 codes. ``recode_nuts2010`` maps
those NUTS 2 codes (a code change only, e.g. EL11 -> EL51) and drops the rest;
``check_greek_codes`` rejects any other old code (e.g. EL300, split into
EL301-EL307); ``hierarchy_gaps`` checks that each level adds up to its parent.

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


def recode_nuts2010(obs: pl.DataFrame) -> pl.DataFrame:
    """Greek NUTS 2010 codes in ``obs`` recoded or removed, so that only current codes
    remain.

    Eurostat publishes 2011 for EL5, EL6 and their NUTS 2 regions only in NUTS 2010
    codes (demo_r_d2jan, demo_r_pjanind2 and demo_r_pjanaggr3, checked 2026-09-29).
    - At NUTS 2 only the code changed (EL11 -> EL51, ...): those are recoded, from
      data/reference/nuts2010_el_recodes.csv (Eurostat's "NUTS 2010 - NUTS 2013"
      correspondence, sheet "Correspondence NUTS-2", all "Code change").
    - EL1 and EL2 shifted boundaries into EL5 and EL6, and NUTS 3 changed too: those
      codes are dropped where they only repeat 2011 or are empty cells.
    An old code with a value in any other year is kept, so that ``check_greek_codes``
    rejects it; two values for one key fail ``validate_observations``.
    """
    recodes = dict(pl.read_csv(REFERENCE / "nuts2010_el_recodes.csv").iter_rows())
    old = pl.col("geo_code").str.starts_with("EL") & ~pl.col("geo_code").is_in(list(greek_nuts()))
    recoded = (
        obs.filter(~(old & pl.col("value").is_null()))
        .with_columns(geo_code=pl.col("geo_code").replace(recodes))
        .filter(~(old & (pl.col("period") == "2011")))
    )
    # The current code has an empty cell where the recoded one has the value.
    key = [k for k in OBSERVATION_KEY if k in recoded.columns]
    return recoded.filter(~(pl.col("value").is_null() & pl.struct(key).is_duplicated()))


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
    geography, where every child has a value (e.g. not for EL in 2011, when EL5 and
    EL6 have none). Status and nature are not part of the match, so a provisional
    child still counts towards a final parent. Returns the offending rows; an empty
    frame means every level adds up.
    """
    keys = [
        k
        for k in OBSERVATION_KEY
        if k not in ("geo_code", "geo_vintage", "scenario_id", "interval")
    ]
    # Interval bounds do not add up across regions; only central values are compared.
    el = obs.filter(
        pl.col("geo_code").str.starts_with("EL")
        & pl.col("value").is_not_null()
        & pl.col("interval").is_null()
    )
    expected = (
        pl.DataFrame({"code": sorted(greek_nuts())})
        .group_by(geo_code=pl.col("code").str.head(-1))
        .agg(expected=pl.len())
    )
    children = (
        el.filter(pl.col("geo_code").str.len_chars() > 2)
        .group_by([*keys, pl.col("geo_code").str.head(-1)])
        .agg(children=pl.col("value").sum(), n=pl.len())
        .join(expected, on="geo_code")
        .filter(pl.col("n") == pl.col("expected"))
    )
    return (
        el.join(children, on=[*keys, "geo_code"], how="inner")
        .filter((pl.col("value") - pl.col("children")).abs() > tolerance)
        .select("geo_code", *keys, "value", "children")
    )


def age_gaps(obs: pl.DataFrame, *, tolerance: float = 0.5) -> pl.DataFrame:
    """Totals that differ from the sum of their age groups.

    For each open age group N+ (e.g. 85+ and 90+), the bands below N that cover ages
    0 to N-1 without a gap, plus N+, plus unknown age, must add up to the total.
    Bands are assumed not to overlap (five-year groups). Central values only. Returns
    the offending totals with the open group and the sum; empty means all add up.
    """
    keys = [k for k in OBSERVATION_KEY if k not in ("age", "interval")]
    rows = obs.filter(pl.col("value").is_not_null() & pl.col("interval").is_null())
    bounds = pl.col("age").str.extract_groups(r"^(\d+)(?:-(\d+)|(\+))$")
    bands = rows.with_columns(
        lo=bounds.struct[0].cast(pl.Int32), hi=bounds.struct[1].cast(pl.Int32)
    ).filter(pl.col("lo").is_not_null())
    closed = bands.filter(pl.col("hi").is_not_null())
    opens = bands.filter(pl.col("hi").is_null()).select(*keys, open="lo", open_value="value")
    below = (
        opens.join(closed, on=keys, nulls_equal=True)
        .filter(pl.col("hi") < pl.col("open"))
        .group_by(*keys, "open")
        .agg(
            bands=pl.col("value").sum(),
            width=(pl.col("hi") - pl.col("lo") + 1).sum(),
            start=pl.col("lo").min(),
        )
    )
    unknown = rows.filter(pl.col("age") == "unknown").select(*keys, unknown="value")
    total = rows.filter(pl.col("age") == "total").select(*keys, total="value")
    return (
        opens.join(below, on=[*keys, "open"], nulls_equal=True)
        .filter((pl.col("start") == 0) & (pl.col("width") == pl.col("open")))
        .join(unknown, on=keys, how="left", nulls_equal=True)
        .join(total, on=keys, nulls_equal=True)  # scenario_id is null
        .with_columns(sum=pl.col("bands") + pl.col("open_value") + pl.col("unknown").fill_null(0))
        .filter((pl.col("total") - pl.col("sum")).abs() > tolerance)
        .select(*keys, "open", "total", "sum")
    )
