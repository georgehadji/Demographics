"""Minimal JSON-stat 2.0 reader for Eurostat dataset responses.

Spec: https://json-stat.org/full/ . Values are stored in row-major order over the
dimensions listed in ``id`` with lengths ``size``. ``value`` and ``status`` may
each be either a dense list or a sparse object keyed by the flat index as a
string. Category ``index`` may be an object (code -> position) or a list of
codes.
"""

from __future__ import annotations

import math
from typing import Any

import polars as pl


def _category_codes(dimension: dict[str, Any]) -> list[str]:
    index = dimension["category"].get("index")
    if index is None:  # single-category dimension may omit index
        return list(dimension["category"]["label"].keys())
    if isinstance(index, list):
        return list(index)
    return [code for code, _ in sorted(index.items(), key=lambda kv: kv[1])]


def _cells(container: list[Any] | dict[str, Any] | None, n: int, dtype: Any) -> pl.Series:
    """``value`` or ``status`` as one entry per cell, null where absent."""
    if container is None:
        return pl.repeat(None, n, dtype=dtype, eager=True)
    if isinstance(container, list):
        return pl.Series(container, dtype=dtype, strict=False)
    positions = pl.Series([int(k) for k in container], dtype=pl.Int64)
    entries = pl.Series(list(container.values()), dtype=dtype, strict=False)
    return pl.repeat(None, n, dtype=dtype, eager=True).scatter(positions, entries)


def to_long(doc: dict[str, Any]) -> pl.DataFrame:
    """Expand a JSON-stat dataset into one row per cell.

    Columns: one String column per dimension id, ``value`` (Float64, null when the
    cell is missing) and ``flag`` (the source status code, e.g. ``p`` provisional).
    Cells that are absent from a sparse ``value`` object are kept as null rows so
    that "not published" stays distinguishable from "not requested".
    """
    if doc.get("class") != "dataset":
        raise ValueError(f"expected a JSON-stat dataset, got class={doc.get('class')!r}")
    ids: list[str] = doc["id"]
    sizes: list[int] = doc["size"]
    codes = [_category_codes(doc["dimension"][d]) for d in ids]
    if [len(c) for c in codes] != sizes:
        raise ValueError("category counts do not match 'size'")

    n = math.prod(sizes)
    flat = pl.int_range(0, n, dtype=pl.Int64, eager=True)
    columns = []
    stride = n
    for d, c in zip(ids, codes, strict=True):
        stride //= len(c)  # row-major: the last dimension varies fastest
        columns.append(pl.Series(d, c, dtype=pl.String).gather((flat // stride) % len(c)))
    columns.append(_cells(doc.get("value"), n, pl.Float64).alias("value"))
    columns.append(_cells(doc.get("status"), n, pl.String).alias("flag"))
    return pl.DataFrame(columns)


def summarize(doc: dict[str, Any]) -> dict[str, Any]:
    """Short structural summary used by the source probe."""
    values = doc.get("value")
    n_values = len(values) if isinstance(values, (list, dict)) else 0
    return {
        "label": doc.get("label"),
        "updated": doc.get("updated"),
        "dimensions": dict(zip(doc.get("id", []), doc.get("size", []), strict=True)),
        "n_values": n_values,
    }
