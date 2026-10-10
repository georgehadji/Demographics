"""Eurostat JSON-stat snapshot -> observations (ADR 0005 anti-corruption layer).

Eurostat codes become the contract's vocabulary here and nowhere else: flags become
``status``, ``nature`` and ``break_in_series``; sex and age codes become ``Sex`` and
``AGE_PATTERN``. An unknown flag or code raises, so a new one is noticed rather than
passed through.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
from typing import Any

import polars as pl

from grpop.definitions import get_definition
from grpop.parse import jsonstat
from grpop.provenance import AGE_TOTAL, Nature, Sex, Status
from grpop.snapshots import Snapshot
from grpop.sources.registry import get_source

TRANSFORM_VERSION = "eurostat_jsonstat@0.1"

_SEX = {"T": Sex.TOTAL.value, "M": Sex.MALE.value, "F": Sex.FEMALE.value}
_OBSERVATION_DIMS = {"geo", "time", "sex", "age"}
_KEY = ["geo", "time", "sex"]


def flag_meaning(flag: str) -> tuple[bool, bool, bool]:
    """Eurostat flag -> (provisional, estimated, break in series).

    Letters before "|" are status flags; after it comes "N" (not for publication) or
    "C" (confidential), which only occur with a missing value. Only the letters seen
    in the ingested datasets are accepted: b, e, p, i (imputed, counted as estimated)
    and u (low reliability, whose value ``to_observations`` leaves out).
    """
    letters, _, confidentiality = flag.partition("|")
    unknown = (set(letters) - set("bepiu")) | (set(confidentiality) - {"N", "C"})
    if unknown:
        raise ValueError(f"unknown Eurostat flag {flag!r}")
    return "p" in letters, bool(set(letters) & {"e", "i"}), "b" in letters


def age(code: str) -> str:
    """Eurostat age code -> contract age (provenance.AGE_PATTERN)."""
    if code == "TOTAL":
        return AGE_TOTAL
    if code == "UNK":
        return "unknown"
    if code == "Y_LT1":
        return "0"
    if m := re.fullmatch(r"Y_LT(\d+)", code):
        return f"0-{int(m[1]) - 1}"
    if m := re.fullmatch(r"Y(\d+)", code):
        return m[1]
    if m := re.fullmatch(r"Y(\d+)-(\d+)", code):
        return f"{m[1]}-{m[2]}"
    if m := re.fullmatch(r"Y_GE(\d+)", code):
        return f"{m[1]}+"
    raise ValueError(f"unknown Eurostat age code {code!r}")


def _resolve_open_age(df: pl.DataFrame) -> pl.DataFrame:
    """Y_OPEN is the open-ended age class; its lower bound varies by country and year.

    The bound is one above the highest single year of age with a value in the same
    geo/time/sex. Y_OPEN cells without a value, or without any single-year ages to
    derive the bound from (in demo_pjan: a few countries before 1993), are dropped:
    their age is unknowable and the TOTAL row still carries the population.
    """
    single = df.filter(pl.col("age").str.contains(r"^Y\d+$") & pl.col("value").is_not_null())
    bound = single.group_by(_KEY).agg(bound=pl.col("age").str.slice(1).cast(pl.Int32).max() + 1)
    is_open = pl.col("age") == "Y_OPEN"
    return (
        df.join(bound, on=_KEY, how="left", maintain_order="left")
        .filter(~is_open | (pl.col("value").is_not_null() & pl.col("bound").is_not_null()))
        .with_columns(
            age=pl.when(is_open)
            .then(pl.lit("Y_GE") + pl.col("bound").cast(pl.String))
            .otherwise(pl.col("age"))
        )
        .drop("bound")
    )


@functools.lru_cache(maxsize=4)
def _parsed(data: bytes) -> tuple[dict[str, Any], pl.DataFrame]:
    """Dataset metadata and long table of a snapshot. Memoized: a build reads several
    series from the same snapshot, and the largest take half a minute to expand."""
    doc = json.loads(data)
    return {k: doc[k] for k in ("id", "dimension", "updated")}, jsonstat.to_long(doc)


def to_observations(
    snapshot: Snapshot,
    data: bytes,
    *,
    definition_id: str,
    nature: Nature,
    geo_vintage: str,
    select: dict[str, str] | None = None,
    geo_prefix: str = "",
) -> pl.DataFrame:
    """One metric of a Eurostat snapshot as observations.

    ``select`` fixes every dimension other than geo, time, sex and age that has more
    than one category (e.g. ``{"indic_de": "TOTFERRT"}``). ``nature`` is the nature of
    an unflagged value; an estimated flag turns ``observed`` into ``official_estimate``.
    ``geo_prefix`` keeps only the geo codes that start with it, before the flags are
    read: a flag is translated, or raises, only where a value is used. A value Eurostat
    flags as of low reliability ("u") is not published: its value is null and its
    status not available (editor's decision, 2026-10-10; hlth_hlye DE 2022).
    """
    if hashlib.sha256(data).hexdigest() != snapshot.sha256:
        raise ValueError("data does not belong to this snapshot")
    doc, df = _parsed(data)
    for dim, code in (select or {}).items():
        if code not in doc["dimension"][dim]["category"]["index"]:
            raise ValueError(f"{code!r} is not a {dim!r} category of {snapshot.source_id}")
        df = df.filter(pl.col(dim) == code).drop(dim)
    df = df.filter(pl.col("geo").str.starts_with(geo_prefix))
    extra = [d for d in doc["id"] if d in df.columns and d not in _OBSERVATION_DIMS]
    for d in extra:
        if df[d].n_unique() > 1:
            raise ValueError(f"select a single {d!r}: {sorted(df[d].unique().to_list())[:10]}")
    df = df.drop(extra)
    if "sex" not in df.columns:
        df = df.with_columns(sex=pl.lit("T"))
    if "age" not in df.columns:
        df = df.with_columns(age=pl.lit("TOTAL"))
    df = _resolve_open_age(df).with_columns(pl.col("flag").fill_null(""))

    meaning = {f: flag_meaning(f) for f in df["flag"].unique().to_list()}
    provisional, estimated, brk = (
        pl.col("flag").replace_strict(
            {f: m[i] for f, m in meaning.items()}, return_dtype=pl.Boolean
        )
        for i in range(3)
    )
    estimated_nature = Nature.OFFICIAL_ESTIMATE if nature is Nature.OBSERVED else nature
    definition = get_definition(definition_id)
    source = get_source(snapshot.source_id)
    return df.select(
        metric=pl.lit(definition.metric),
        definition_id=pl.lit(definition.id),
        geo_code=pl.col("geo"),
        geo_vintage=pl.lit(geo_vintage),
        period=pl.col("time"),
        sex=pl.col("sex").replace_strict(_SEX),
        age=pl.col("age").replace_strict({c: age(c) for c in df["age"].unique().to_list()}),
        value=pl.when(pl.col("flag").str.contains("u", literal=True))
        .then(None)
        .otherwise(pl.col("value")),
        unit=pl.lit(definition.unit),
        source=pl.lit(source.provider),
        dataset_code=pl.lit(source.dataset_code),
        source_url=pl.lit(snapshot.source_url),
        vintage=pl.lit(doc["updated"]),
        retrieved_at=pl.lit(snapshot.retrieved_at, dtype=pl.Datetime("us", "UTC")),
        transform_version=pl.lit(TRANSFORM_VERSION),
        nature=pl.when(estimated)
        .then(pl.lit(estimated_nature.value))
        .otherwise(pl.lit(nature.value)),
        status=pl.when(pl.col("value").is_null() | pl.col("flag").str.contains("u", literal=True))
        .then(pl.lit(Status.NOT_AVAILABLE.value))
        .when(provisional)
        .then(pl.lit(Status.PROVISIONAL.value))
        .otherwise(pl.lit(Status.FINAL.value)),
        break_in_series=brk,
        scenario_id=pl.lit(None, dtype=pl.String),
        interval=pl.lit(None, dtype=pl.String),
    )
