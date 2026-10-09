"""ELSTAT natural movement press release, on the recorded 2025 release: its values, and
each self-check, by changing one number of its text."""

import dataclasses
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from test_indicators import data

from grpop import reconcile
from grpop.harmonize import REFERENCE
from grpop.parse import elstat_pdf
from grpop.provenance import validate_observations
from grpop.snapshots import Snapshot

RAW = (Path(__file__).parent / "fixtures" / "elstat_spo03_2025.pdf").read_bytes()
SNAP = Snapshot(
    hashlib.sha256(RAW).hexdigest(),
    elstat_pdf.SOURCE_ID,
    "https://example.org/x",
    datetime(2026, 10, 6, tzinfo=UTC),
    len(RAW),
)
TEXT = elstat_pdf.pages(RAW)


@pytest.fixture(scope="module")
def release() -> pl.DataFrame:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(elstat_pdf, "pages", lambda _: TEXT)  # read once, above
        return validate_observations(elstat_pdf.to_observations(SNAP, RAW))


def test_the_recorded_2025_release(release):
    df = release
    key = df["definition_id"] + " " + df["period"] + " " + df["sex"] + " " + df["age"]
    value = dict(zip(key + " " + df["geo_code"], df["value"], strict=True))
    status = dict(zip(key + " " + df["geo_code"], df["status"], strict=True))
    assert (df.height, set(df["vintage"])) == (570, {"2026-10-01"})
    assert value["natural_change@v1 2025 total total EL"] == -56223
    assert status["deaths@v1 2023 total total EL"] == "revised"
    assert value["live_births@v1 2025 total total EL531"] == 719 + 109  # Κοζάνη + Γρεβενά
    assert value["live_births@v1 2025 total 0-14 EL"] == 95  # mother under 15
    assert value["live_births@v1 1985 total unknown EL"] == 46
    assert value["live_births@v1 1995 total unknown EL"] == 0  # "-"
    assert value["live_births@v1 2025 male total EL"] == 33633
    assert value["live_births_foreign_citizen_mother@v1 2025 total total EL"] == 6644
    assert value["live_births_outside_marriage@v1 2025 total total EL"] == 6667
    assert value["deaths@v1 2025 male 0 EL"] == 115
    assert value["deaths@v1 2017 total 0 EL"] == 306  # Table 7 only
    assert value["deaths@v1 2025 female 100+ EL"] == 864
    assert value["infant_mortality_rate@v1 2025 total total EL"] == 3.2
    assert value["live_births_caesarean@v1 2025 total total EL"] == 41202
    assert value["live_births_normal_delivery@v1 2021 total total EL"] == 33604
    assert value["marriages@v1 1932 total total EL"] == 39283
    assert "civil_marriages@v1 1981 total total EL" not in value  # "-": none yet
    assert value["civil_partnerships@v1 2025 total total EL"] == 16627
    assert value["first_marriages@v1 2025 female 0-19 EL"] == 355
    assert value["first_marriages@v1 2025 male total EL"] == 31730
    assert value["divorces@v1 2025 total total EL"] == 15853
    assert value["divorces_per_100_marriages@v1 2025 total total EL"] == 43.1
    assert value["divorced_persons@v1 2025 female 65+ EL"] == 636
    assert value["live_births_outside_marriage_share@v1 2025 total total EL"] == 10.2
    assert value["caesarean_share@v1 2025 total total EL"] == 62.8
    broken = df.filter(pl.col("break_in_series"))
    assert sorted(zip(broken["definition_id"], broken["period"], strict=True)) == [
        ("perinatal_mortality_rate@v1", "2019"),
        ("stillbirths@v1", "2019"),
    ]
    rates = df.filter(pl.col("definition_id").str.contains("rate"))
    assert set(rates["nature"]) == {"official_estimate"}
    assert set(df.filter(pl.col("unit").str.starts_with("per "))["nature"]) == {"official_estimate"}


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        ("Χίος 350 -12,3%", "Χίος 351 -12,3%", "regional units do not add up"),
        ("Εξωτερικό 167 ", "Εξωτερικό 168 ", "regions and abroad"),
        ("2024 68.467 126.916 -58.449", "2024 68.467 126.916 -58.448", "births minus deaths"),
        ("<15 93 58 60 51 95", "<15 93 58 60 51 96", "Table 3 2025: age groups"),
        ("Αγόρια 43.998", "Αγόρια 43.999", "boys \\+ girls"),
        ("Κάτω του έτους 261 149 112", "Κάτω του έτους 261 150 112", "men \\+ women"),
        ("2025 65.618 422 208 3,2", "2025 65.618 422 208 3,3", "infant mortality"),
        ("* Το 2019, το όριο", "* Το όριο", "stillbirth break"),  # noqa: RUF001
        ("Καισαρική Τομή 51.607", "Καισαρική Τομή 51.608", "Table 5 2021: methods"),
        ("2025 53.437 36.810 20.868", "2025 53.437 36.810 20.869", "religious \\+ civil"),
        ("16.627 31,1", "16.628 31,1", "marriages \\+ partnerships"),
        ("<20 89 0,3 355 1,1", "<20 90 0,3 355 1,1", "Table 9 male: age groups"),
        ("42,4 43,1", "42,4 43,2", "divorces per 100 marriages"),
        ("Σύνολο 15.532 100,0", "Σύνολο 15.533 100,0", "Table 11 2024: total"),
        ("10+ έτη 10.314", "10+ έτη 10.315", "Table 11 2024: duration"),
        ("65+ 1.322 8,3", "65+ 1.323 8,3", "Table 12 2025: men \\+ women"),
        ("9,2 9,8 9,7 9,9 10,2", "9,2 9,8 9,7 9,9 10,3", "Table 4 2025: share outside"),
        ("2025 37,1 62,8", "2025 37,1 62,9", "Graph 3 2025: normal, caesarean"),
    ],
)
def test_a_release_that_does_not_add_up_stops(monkeypatch, old, new, error):
    changed = [page.replace(old, new) for page in TEXT]
    assert changed != TEXT, old
    monkeypatch.setattr(elstat_pdf, "pages", lambda _: changed)
    with pytest.raises(ValueError, match=error):
        elstat_pdf.to_observations(SNAP, RAW)


def test_reference_labels_are_greek_nuts_2024_codes():
    areas = pl.read_csv(REFERENCE / "elstat_areas_el.csv", schema_overrides={"geo_code": pl.String})
    nuts = set(pl.read_csv(REFERENCE / "nuts2024_el.csv")["geo_code"])
    assert set(areas["geo_code"].drop_nulls()) <= nuts
    assert areas["label_el"].is_unique().all()


@pytest.mark.parametrize("definition_id", list(reconcile.CHECKS))
def test_elstat_agrees_with_eurostat_except_where_explained(release, definition_id):
    """On the recorded Eurostat tables (Greece, 2021 onwards)."""
    ours = release.filter(pl.col("definition_id") == definition_id)
    sources = reconcile.sources(definition_id)
    reconcile.check(definition_id, ours, data(sources))
    # a listed difference that is no longer listed stops it
    first = reconcile.CHECKS[definition_id]
    known = sorted(first.known_differences)
    if not known:  # equal wherever both publish
        return
    unlisted = dataclasses.replace(first, known_differences=frozenset(known[:-1]))
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(reconcile.CHECKS, definition_id, unlisted)
        with pytest.raises(ValueError, match="differ where nothing explains it"):
            reconcile.check(definition_id, ours, data(sources))
