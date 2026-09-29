"""Minimal JSON-stat 2.0 reader for Eurostat dataset responses.

Spec: https://json-stat.org/full/ . Values are stored in row-major order over the
dimensions listed in ``id`` with lengths ``size``. ``value`` and ``status`` may
each be either a dense list or a sparse object keyed by the flat index as a
string. Category ``index`` may be an object (code -> position) or a list of
codes.
"""

from __future__ import annotations

from itertools import product
from typing import Any

import polars as pl


def _category_codes(dimension: dict[str, Any]) -> list[str]:
    index = dimension["category"].get("index")
    if index is None:  # single-category dimension may omit index
        return list(dimension["category"]["label"].keys())
    if isinstance(index, list):
        return list(index)
    return [code for code, _ in sorted(index.items(), key=lambda kv: kv[1])]


def _lookup(container: list[Any] | dict[str, Any] | None, flat_index: int) -> Any:
    if container is None:
        return None
    if isinstance(container, list):
        return container[flat_index]
    return container.get(str(flat_index))


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

    values, statuses = doc.get("value"), doc.get("status")
    rows = []
    for flat, combo in enumerate(product(*codes)):
        raw = _lookup(values, flat)
        rows.append((*combo, None if raw is None else float(raw), _lookup(statuses, flat)))

    schema = {d: pl.String for d in ids} | {"value": pl.Float64, "flag": pl.String}
    return pl.DataFrame(rows, schema=schema, orient="row")


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
