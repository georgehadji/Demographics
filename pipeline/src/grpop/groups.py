"""Peer groups (PROPOSAL §6) and the EU-27 median, which Eurostat does not publish.

Members are in ``data/reference/peer_groups.csv``, one version per group:

- ``eu27``: the EU-27 since 2020, the members of Eurostat's EU27_2020.
- ``southern_europe``: as PROPOSAL §6 lists it; Greece is the focus, not a peer.
- ``south_east_europe``: the EU members and candidates of the Balkan peninsula that
  Eurostat's demography tables cover. Bosnia and Herzegovina and Kosovo are left out:
  demo_find has no total fertility rate for them from 2020 (checked 2026-10-03).
- ``very_low_fertility``: EU-27 members whose total fertility rate (demo_find TOTFERRT)
  is below ``RULE`` in its year. The list is pinned and the build checks it against the
  rule, so a revision of the data that changes it stops the build until a new version
  of the group is recorded.

A change of members bumps the group's version.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from grpop.harmonize import REFERENCE
from grpop.provenance import Nature, Status

GROUPS = pl.read_csv(REFERENCE / "peer_groups.csv", schema_overrides={"version": pl.String})
RULE: dict[str, Any] = {"group": "very_low_fertility", "below": 1.3, "period": "2024"}
MEDIAN_GEO = "EU27_2020_MEDIAN"  # geo_code of the median of the eu27 members
MEDIAN_VERSION = "eu27_median@0.1"


def members(group: str) -> list[str]:
    codes = GROUPS.filter(pl.col("group") == group)["geo_code"].to_list()
    if not codes:
        raise ValueError(f"unknown peer group {group!r}")
    return codes


def median(df: pl.DataFrame) -> pl.DataFrame:
    """The median of the eu27 members' values, as ``derived`` rows with geo_code
    ``MEDIAN_GEO``; only where every member has a value. ``df`` is one data product
    step, so all its rows share one definition_id (PROPOSAL §6: compare only those)."""
    if df["definition_id"].n_unique() > 1:
        raise ValueError("a median mixes definitions")
    eu = members("eu27")
    key = ["period", "sex", "age", "interval"]
    first = [
        c for c in df.columns if c not in {*key, "geo_code", "value", "status", "break_in_series"}
    ]
    return (
        df.filter(pl.col("geo_code").is_in(eu) & pl.col("value").is_not_null())
        .group_by(key)
        .agg(
            pl.col(first).first(),
            n=pl.len(),
            value=pl.col("value").median(),
            provisional=(pl.col("status") == Status.PROVISIONAL.value).any(),
            break_in_series=pl.col("break_in_series").any(),
        )
        .filter(pl.col("n") == len(eu))
        .with_columns(
            geo_code=pl.lit(MEDIAN_GEO),
            nature=pl.lit(Nature.DERIVED.value),
            transform_version=pl.lit(MEDIAN_VERSION),
            status=pl.when(pl.col("provisional"))
            .then(pl.lit(Status.PROVISIONAL.value))
            .otherwise(pl.lit(Status.FINAL.value)),
        )
        .select(df.columns)
    )


def with_median(df: pl.DataFrame) -> pl.DataFrame:
    return pl.concat([df, median(df)])


def check(population: pl.DataFrame, fertility: pl.DataFrame) -> dict[str, Any]:
    """Every member has a population value, and very_low_fertility follows its rule.
    Returns the groups as the data product publishes them."""
    present = set(population.filter(pl.col("value").is_not_null())["geo_code"])
    missing = sorted(set(GROUPS["geo_code"]) - present)
    if missing:
        raise ValueError(f"peer group members without a population value: {missing}")
    year = fertility.filter(
        (pl.col("period") == RULE["period"])
        & pl.col("geo_code").is_in(members("eu27"))
        & pl.col("value").is_not_null()
    )
    if year.height != len(members("eu27")):
        raise ValueError(f"{RULE['group']}: the eu27 rates of {RULE['period']} are incomplete")
    ruled = sorted(year.filter(pl.col("value") < RULE["below"])["geo_code"])
    if ruled != sorted(members(RULE["group"])):
        raise ValueError(f"{RULE['group']}: the rule now gives {ruled}; record a new version")
    return {
        "rule": RULE,
        "groups": {
            g: {"version": d["version"][0], "members": sorted(d["geo_code"])}
            for (g,), d in GROUPS.group_by("group", maintain_order=True)
        },
    }
