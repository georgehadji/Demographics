"""Prototype reader for ELSTAT table SPO18/10: population on 1 January, 2002 onwards.

Phase 0 spike (IMPLEMENTATION-PLAN A2); findings in docs/spikes/elstat-ingestion.md.
Only the country total and the 13 regions (NUTS 2) are read. Regional units need
the concordance of step B5. The male/female sheets are not read yet.

The workbook is laid out for print, so everything is located by content, never by
row number: the header row is the one with "1.1.YYYY" cells, footnote markers are
read from each sheet's own footnotes (their meaning differs between sheets), and
rows are matched on the English label in the last text column.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime

import fastexcel
import polars as pl

from grpop.definitions import get_definition
from grpop.harmonize import REFERENCE
from grpop.provenance import AGE_TOTAL, Sex
from grpop.sources.registry import get_source

# Source metadata comes from registry.yaml and the metric from definitions.yaml;
# only the ids are named here.
SOURCE_ID = "elstat_spo18_t10"
DEFINITION_ID = "population_1jan@v1"
TRANSFORM_VERSION = "elstat_spo18_t10@0.1"

_YEAR_CELL = re.compile(r"^\s*1\.1\.(\d{4})\s*(\**)\s*$")
_FOOTNOTE = re.compile(r"^\s*(\*+)\s*(.+)$")
_REVISED = re.compile(r"revised|αναθεωρημ", re.IGNORECASE)
_TRAILING_MARKERS = re.compile(r"[\s*\d()]+$")

Row = list[str | None]


def normalise_label(text: str) -> str:
    """Upper-case, drop punctuation and trailing footnote markers, collapse spaces."""
    text = _TRAILING_MARKERS.sub("", text.upper())
    return " ".join(re.sub(r"[,&]", " ", text).split())


def region_codes() -> tuple[dict[str, str], str]:
    """(English ELSTAT label (normalised) -> NUTS code, NUTS vintage) from the reference CSV."""
    with (REFERENCE / "elstat_regions_nuts.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    vintages = {r["geo_vintage"] for r in rows}
    if len(vintages) != 1:
        raise ValueError(f"elstat_regions_nuts.csv mixes NUTS vintages: {sorted(vintages)}")
    return {normalise_label(r["label_en"]): r["geo_code"] for r in rows}, vintages.pop()


def _is_number(cell: str) -> bool:
    try:
        float(cell)
    except ValueError:
        return False
    return True


def _english_label(row: Row) -> str | None:
    texts = [c for c in row[1:] if c and not _is_number(c)]
    return texts[-1] if texts else None


def parse_sheet(rows: list[Row], geo: dict[str, str]) -> pl.DataFrame:
    """One sheet of table 10 -> (geo_code, period, value, status) for NUTS 0/2 rows.

    Raises ``ValueError`` if the layout no longer matches: no year header, a
    non-numeric value, or a missing or duplicated region.
    """
    header = next(
        (i for i, r in enumerate(rows) if any(c and _YEAR_CELL.match(c) for c in r)), None
    )
    if header is None:
        raise ValueError("no '1.1.YYYY' header row")
    years = {j: m.groups() for j, c in enumerate(rows[header]) if c and (m := _YEAR_CELL.match(c))}
    revised_marks = {
        m.group(1)
        for r in rows[header + 1 :]
        if r[0] and (m := _FOOTNOTE.match(r[0])) and _REVISED.search(m.group(2))
    }

    out = []
    seen: set[str] = set()
    for r in rows[header + 1 :]:
        label = _english_label(r)
        code = geo.get(normalise_label(label)) if label else None
        if code is None:
            continue  # regional units, footnotes, blank rows
        if code in seen:
            raise ValueError(f"region {code} appears twice")
        seen.add(code)
        for j, (year, mark) in years.items():
            cell = r[j]
            if cell is None or not _is_number(cell):
                raise ValueError(f"non-numeric value {cell!r} for {code} {year}")
            status = "revised" if mark and mark in revised_marks else "final"
            out.append((code, year, float(cell), status))

    missing = set(geo.values()) - seen
    if missing:
        raise ValueError(f"regions not found: {sorted(missing)}")
    return pl.DataFrame(
        out, schema=["geo_code", "period", "value", "status"], orient="row"
    ).with_columns(pl.col("value").cast(pl.Float64))


def read_population_1jan(
    xlsx: bytes, *, source_url: str, retrieved_at: datetime, vintage: str
) -> pl.DataFrame:
    """Table 10 workbook -> observations for the country and the 13 regions."""
    if retrieved_at.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    source = get_source(SOURCE_ID)
    definition = get_definition(DEFINITION_ID)
    geo, geo_vintage = region_codes()
    reader = fastexcel.read_excel(xlsx)
    frames = []
    for name in reader.sheet_names:
        if not name.startswith("ΣΥΝΟΛΟ-TOTAL"):
            continue  # male/female sheets not parsed yet: only totals are read
        sheet = reader.load_sheet(name, header_row=None, dtypes="string").to_polars()
        frames.append(parse_sheet([list(r) for r in sheet.iter_rows()], geo))
    if not frames:
        raise ValueError("no 'ΣΥΝΟΛΟ-TOTAL' sheets found")

    return pl.concat(frames).with_columns(
        metric=pl.lit(definition.metric),
        definition_id=pl.lit(definition.id),
        geo_vintage=pl.lit(geo_vintage),
        unit=pl.lit(definition.unit),
        source=pl.lit(source.provider),
        dataset_code=pl.lit(source.dataset_code),
        source_url=pl.lit(source_url),
        vintage=pl.lit(vintage),
        sex=pl.lit(Sex.TOTAL.value),
        age=pl.lit(AGE_TOTAL),
        retrieved_at=pl.lit(retrieved_at, dtype=pl.Datetime("us", "UTC")),
        transform_version=pl.lit(TRANSFORM_VERSION),
        nature=pl.lit("official_estimate"),
        break_in_series=pl.lit(False),  # ponytail: break footnotes are not read yet
        scenario_id=pl.lit(None, dtype=pl.String),
    )
