"""ELSTAT natural movement of population, the yearly press release (SPO03) -> observations.

Reads the counts of Table 1 (births, deaths and natural change of Greece, 1932 onwards
with gaps) and Table 2 (births and deaths of the latest year by place of usual
residence: regions and regional units), never the % columns or the prose. Located by
content: each table by its title, each row by its year or its label
(data/reference/elstat_areas_el.csv). The release is checked against itself, and
anything that does not add up raises: births minus deaths equal natural change in every
year of Table 1; the country row of Table 2 equals Table 1; the regions plus "Εξωτερικό"
(residence abroad, read for this check only) add up to the country; and each region's
regional units add up to the region, except Attica, given as a whole. Regional units
that NUTS 2024 merges into one NUTS 3 region are summed into a ``derived`` value.
"""

from __future__ import annotations

import io
import re

import pdfplumber
import polars as pl

from grpop.definitions import get_definition
from grpop.harmonize import REFERENCE
from grpop.provenance import AGE_TOTAL, Nature, Sex, Status
from grpop.snapshots import Snapshot
from grpop.sources.registry import get_source

SOURCE_ID = "elstat_spo03_2025"
TRANSFORM_VERSION = "elstat_spo03_pdf@0.1"
BIRTHS, DEATHS, NATURAL_CHANGE = "live_births@v1", "deaths@v1", "natural_change@v1"

_MONTHS = [
    "Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου",
    "Ιουλίου", "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου",
]  # fmt: skip
_DATE = re.compile(r"Πειραιάς,\s+(\d{1,2})\s+(\w+)\s+(\d{4})")
_NUM = r"-?\d{1,3}(?:\.\d{3})*"  # Greek thousands separator
_TABLE1 = re.compile(rf"^(\d{{4}}) ({_NUM}) ({_NUM})(\*?) ({_NUM})$")
_PCT = r"-?\d+,\d%"
_TABLE2 = re.compile(rf"^(.+?) ({_NUM}) {_PCT} ({_NUM}) {_PCT}$")
_TABLE2_YEAR = re.compile(r"έτους (\d{4})")


def _int(text: str) -> int:
    return int(text.replace(".", ""))


def pages(pdf: bytes) -> list[str]:
    """The text of each page, line by line as printed."""
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return [page.extract_text() or "" for page in doc.pages]


def release_date(text: list[str]) -> str:
    """The date on the first page, ISO 8601: the vintage of every value."""
    m = _DATE.search(text[0])
    if not m or m.group(2) not in _MONTHS:
        raise ValueError("no release date 'Πειραιάς, <day> <month> <year>' on page 1")
    return f"{m.group(3)}-{_MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}"


def _table(text: list[str], title: str) -> list[str]:
    found = [p for p in text if title in p]
    if len(found) != 1:
        raise ValueError(f"'{title}' on {len(found)} pages, expected one")
    lines = found[0].splitlines()
    return lines[next(i for i, line in enumerate(lines) if title in line) :]


def table1(text: list[str]) -> pl.DataFrame:
    """Greece by year: births, deaths, natural change, and whether deaths are revised."""
    lines = _table(text, "Πίνακας 1.")
    rows = [m.groups() for line in lines if (m := _TABLE1.match(line.strip()))]
    if not rows:
        raise ValueError("Table 1: no year rows")
    marked = any(r[3] for r in rows)
    note = next((line for line in lines if line.startswith("*")), "")
    if marked and "αναθεωρ" not in note:
        raise ValueError(f"Table 1: '*' marks a value but the note is not a revision: {note!r}")
    df = pl.DataFrame(
        [(y, _int(b), _int(d), bool(star), _int(n)) for y, b, d, star, n in rows],
        schema=["period", "births", "deaths", "revised", "natural_change"],
        orient="row",
    )
    wrong = df.filter(pl.col("births") - pl.col("deaths") != pl.col("natural_change"))
    if wrong.height:
        raise ValueError(f"Table 1: births minus deaths differ from natural change:\n{wrong}")
    return df


def table2(text: list[str]) -> tuple[str, pl.DataFrame]:
    """The year of Table 2, and its rows: label, births, deaths, in printed order."""
    lines = _table(text, "Πίνακας 2.")
    year = _TABLE2_YEAR.search(" ".join(lines[:3]))
    if not year:
        raise ValueError("Table 2: no 'έτους YYYY' in its title")
    rows = [m.groups() for line in lines if (m := _TABLE2.match(line.strip()))]
    df = pl.DataFrame(
        [(label, _int(b), _int(d)) for label, b, d in rows],
        schema=["label_el", "births", "deaths"],
        orient="row",
    )
    return year.group(1), df


def _areas(rows: pl.DataFrame) -> pl.DataFrame:
    """Rows of Table 2 with their NUTS code and level, after the adds-up checks."""
    areas = pl.read_csv(REFERENCE / "elstat_areas_el.csv", schema_overrides={"geo_code": pl.String})
    unknown = set(rows["label_el"]) - set(areas["label_el"])
    missing = set(areas["label_el"]) - set(rows["label_el"])
    if unknown or missing or rows["label_el"].is_duplicated().any():
        raise ValueError(f"Table 2: labels unknown {sorted(unknown)}, missing {sorted(missing)}")
    df = rows.join(areas, on="label_el").with_columns(level=pl.col("geo_code").str.len_chars() - 2)
    counts = ["births", "deaths"]
    country = df.filter(pl.col("geo_code") == "EL").select(counts)
    regions = df.filter((pl.col("level") == 2) | pl.col("geo_code").is_null()).select(counts).sum()
    if not country.equals(regions):
        raise ValueError(
            f"Table 2: regions and abroad {regions.row(0)} != country {country.row(0)}"
        )
    units = (
        df.filter(pl.col("level") == 3)
        .group_by(parent=pl.col("geo_code").str.head(4))
        .agg(pl.col(c).sum().alias(f"{c}_units") for c in counts)
        .join(df, left_on="parent", right_on="geo_code")
        .filter(
            (pl.col("births") != pl.col("births_units"))
            | (pl.col("deaths") != pl.col("deaths_units"))
        )
    )
    if units.height:
        raise ValueError(f"Table 2: regional units do not add up to their region:\n{units}")
    return df


def to_observations(snapshot: Snapshot, pdf: bytes) -> pl.DataFrame:
    """Births, deaths and natural change of Greece (Table 1), and births and deaths of
    the regions and NUTS 3 regions (Table 2)."""
    text = pages(pdf)
    national = table1(text)
    year, rows = table2(text)
    areas = _areas(rows)
    if (
        not areas.filter(pl.col("geo_code") == "EL")
        .select("births", "deaths")
        .equals(national.filter(pl.col("period") == year).select("births", "deaths"))
    ):
        raise ValueError(f"Table 2: the country row differs from Table 1 for {year}")
    regional = (
        areas.filter(pl.col("level") >= 2)
        .group_by("geo_code")
        .agg(pl.col("births", "deaths").sum(), merged=pl.len() > 1)
        .with_columns(
            period=pl.lit(year),
            nature=pl.when("merged")
            .then(pl.lit(Nature.DERIVED.value))
            .otherwise(pl.lit(Nature.OBSERVED.value)),
            revised=pl.lit(False),
        )
    )
    long = pl.concat(
        [
            national.select(
                "period",
                geo_code=pl.lit("EL"),
                definition_id=pl.lit(d),
                value=c,
                nature=pl.lit(Nature.OBSERVED.value),
                revised=pl.col("revised") if c != "births" else pl.lit(False),
            )
            for d, c in ((BIRTHS, "births"), (DEATHS, "deaths"), (NATURAL_CHANGE, "natural_change"))
        ]
        + [
            regional.select(
                "period",
                "geo_code",
                definition_id=pl.lit(d),
                value=c,
                nature="nature",
                revised="revised",
            )
            for d, c in ((BIRTHS, "births"), (DEATHS, "deaths"))
        ]
    )
    source = get_source(SOURCE_ID)
    metric = {d: get_definition(d).metric for d in (BIRTHS, DEATHS, NATURAL_CHANGE)}
    unit = {d: get_definition(d).unit for d in (BIRTHS, DEATHS, NATURAL_CHANGE)}
    return long.select(
        metric=pl.col("definition_id").replace_strict(metric),
        definition_id="definition_id",
        geo_code="geo_code",
        geo_vintage=pl.lit("NUTS2024"),
        period="period",
        sex=pl.lit(Sex.TOTAL.value),
        age=pl.lit(AGE_TOTAL),
        value=pl.col("value").cast(pl.Float64),
        unit=pl.col("definition_id").replace_strict(unit),
        source=pl.lit(source.provider),
        dataset_code=pl.lit(source.dataset_code),
        source_url=pl.lit(snapshot.source_url),
        vintage=pl.lit(release_date(text)),
        retrieved_at=pl.lit(snapshot.retrieved_at, dtype=pl.Datetime("us", "UTC")),
        transform_version=pl.lit(TRANSFORM_VERSION),
        nature="nature",
        status=pl.when("revised")
        .then(pl.lit(Status.REVISED.value))
        .otherwise(pl.lit(Status.FINAL.value)),
        break_in_series=pl.lit(False),
        scenario_id=pl.lit(None, dtype=pl.String),
        interval=pl.lit(None, dtype=pl.String),
    ).sort("definition_id", "geo_code", "period")
