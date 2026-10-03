"""UN WPP 2024 probabilistic projection of total population (PPP/POPTOT) -> observations.

One sheet per quantile: the median is the central value, the 80% and 95% bounds are
``interval`` rows (ADR 0007). Values are thousands as of 1 July
(``population_1jul@v1``), written in persons. Areas are matched on the ISO2 code,
which is Eurostat's geo code except where ``data/reference/iso2_eurostat.csv`` says
otherwise. The header row is found by its content, never by its number.
"""

from __future__ import annotations

import fastexcel
import polars as pl

from grpop.definitions import get_definition
from grpop.harmonize import REFERENCE
from grpop.provenance import AGE_TOTAL, Interval, Nature, Sex, Status
from grpop.snapshots import Snapshot
from grpop.sources.registry import get_source

SOURCE_ID = "un_wpp_2024_ppp_poptot"
DEFINITION_ID = "population_1jul@v1"
TRANSFORM_VERSION = "un_wpp_xlsx@0.1"
VINTAGE = "WPP 2024"
SHEETS = {
    "Median": None,
    "Lower 80": Interval.LOWER_80,
    "Upper 80": Interval.UPPER_80,
    "Lower 95": Interval.LOWER_95,
    "Upper 95": Interval.UPPER_95,
}
_ISO2 = "ISO2 Alpha-code"


def _sheet(reader: fastexcel.ExcelReader, name: str) -> pl.DataFrame:
    raw = reader.load_sheet(name, header_row=None, dtypes="string").to_polars()
    header = next(i for i in range(raw.height) if _ISO2 in raw.row(i))
    names = [str(c) for c in raw.row(header)]
    years = [n for n in names if n.isdigit()]
    return (
        raw.slice(header + 1)
        .rename(dict(zip(raw.columns, names, strict=True)))
        .filter(pl.col(_ISO2).str.contains(r"^[A-Z]{2}$"))  # countries; regions have none
        .unpivot(years, index=_ISO2, variable_name="period", value_name="value")
        .with_columns(value=(pl.col("value").cast(pl.Float64) * 1000).round(0))
    )


def to_observations(snapshot: Snapshot, data: bytes, geo_codes: set[str]) -> pl.DataFrame:
    """The areas in ``geo_codes`` (Eurostat codes), every year and quantile."""
    reader = fastexcel.read_excel(data)
    if set(SHEETS) - set(reader.sheet_names):
        raise ValueError(f"{SOURCE_ID}: sheets {sorted(SHEETS)} expected, got {reader.sheet_names}")
    iso2 = dict(pl.read_csv(REFERENCE / "iso2_eurostat.csv").iter_rows())
    definition, source = get_definition(DEFINITION_ID), get_source(SOURCE_ID)
    frames = [
        _sheet(reader, name).with_columns(
            interval=pl.lit(interval.value if interval else None, dtype=pl.String)
        )
        for name, interval in SHEETS.items()
    ]
    return (
        pl.concat(frames)
        .with_columns(geo_code=pl.col(_ISO2).replace(iso2))
        .filter(pl.col("geo_code").is_in(geo_codes))
        .select(
            metric=pl.lit(definition.metric),
            definition_id=pl.lit(definition.id),
            geo_code="geo_code",
            geo_vintage=pl.lit("ISO 3166-1"),
            period="period",
            sex=pl.lit(Sex.TOTAL.value),
            age=pl.lit(AGE_TOTAL),
            value="value",
            unit=pl.lit(definition.unit),
            source=pl.lit(source.provider),
            dataset_code=pl.lit(source.dataset_code),
            source_url=pl.lit(snapshot.source_url),
            vintage=pl.lit(VINTAGE),
            retrieved_at=pl.lit(snapshot.retrieved_at, dtype=pl.Datetime("us", "UTC")),
            transform_version=pl.lit(TRANSFORM_VERSION),
            nature=pl.lit(Nature.PROJECTED.value),
            status=pl.lit(Status.FINAL.value),
            break_in_series=pl.lit(False),
            scenario_id=pl.lit(None, dtype=pl.String),
            interval="interval",
        )
    )
