"""Tests for the ELSTAT table SPO18/10 prototype reader.

The fixture is a recorded response, not hand-written: the workbook as downloaded
from ELSTAT on 2026-09-28 (portal documentID 116985, file
A1605_SPO18_TS_AN_00_2002_00_2025_10_F_BI.xlsx, sha256 fd7692db...b713f1).
"""

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from grpop.provenance import validate_observations
from grpop.sources.elstat_xlsx import normalise_label, parse_sheet, read_population_1jan

FIXTURE = Path(__file__).parent / "fixtures" / "elstat_spo18_t10_2025.xlsx"


@pytest.fixture(scope="module")
def observations():
    return read_population_1jan(
        FIXTURE.read_bytes(),
        source_url="https://www.statistics.gr/el/statistics/-/publication/SPO18/2025",
        retrieved_at=datetime(2026, 9, 28, 12, 0, tzinfo=UTC),
        vintage="SPO18 table 10, 2025 edition",
    )


def test_output_passes_the_provenance_contract(observations):
    validate_observations(observations)


def test_country_and_all_regions_for_every_year(observations):
    assert observations["geo_code"].n_unique() == 14  # EL + 13 NUTS 2 regions
    assert observations["period"].n_unique() == 24  # 1.1.2002 .. 1.1.2025
    assert observations.height == 14 * 24


def test_regions_sum_to_the_country_total(observations):
    regions = observations.filter(observations["geo_code"] != "EL")
    by_year = regions.group_by("period").agg(regions_sum=pl.col("value").sum())
    totals = observations.filter(observations["geo_code"] == "EL").join(by_year, on="period")
    assert (totals["value"] == totals["regions_sum"]).all()


def test_revised_flags_follow_each_sheets_own_footnotes(observations):
    status = dict(
        observations.filter(observations["geo_code"] == "EL").select("period", "status").iter_rows()
    )
    # 2002-2013 sheet: "**" = revised, "*" = Mount Athos included (must not count).
    assert status["2011"] == "final"
    assert status["2013"] == "revised"
    # 2014-2025 sheet: "*" = revised.
    assert status["2014"] == "revised"
    assert status["2022"] == "final"
    assert status["2025"] == "final"


def test_label_normalisation_handles_markers_and_spelling():
    assert normalise_label("FORMER PERFECTURE OF KYKLADES3") == "FORMER PERFECTURE OF KYKLADES"
    assert normalise_label("IONIAN  ISLANDS") == "IONIAN ISLANDS"
    assert normalise_label("ANATOLIKI MAKEDONIA, THRAKI") == "ANATOLIKI MAKEDONIA THRAKI"


def test_layout_changes_are_errors_not_silent_gaps():
    # Hand-written rows in the shape of the real sheet; only the English label
    # (last text cell) is matched, so the Greek label is illustrative.
    geo = {"TOTAL": "EL", "KRITI": "EL43"}
    good = [
        [None, "1.1.2024*", "1.1.2025"],
        ["Σύνολο", "10", "11", "TOTAL"],
        ["Κρήτη", "4", "5", "KRITI"],
        ["* Αναθεωρημένα στοιχεία", "* Revised data"],
    ]
    parsed = parse_sheet(good, geo)
    assert parsed.height == 4
    assert set(parsed.filter(pl.col("period") == "2024")["status"]) == {"revised"}

    with pytest.raises(ValueError, match="not found"):
        parse_sheet(good[:2] + good[3:], geo)
    with pytest.raises(ValueError, match="non-numeric"):
        parse_sheet([good[0], good[1], ["Κρήτη", "4", "-", "KRITI"]], geo)
    with pytest.raises(ValueError, match="header"):
        parse_sheet(good[1:], geo)
