"""ELSTAT natural movement press release: the recorded 2025 release, and hand-written
page text in its layout (Tables 1 and 2 as pdfplumber prints them, made-up counts that
add up, not ELSTAT data) for the cases a real release does not show.
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from grpop.harmonize import REFERENCE
from grpop.parse import elstat_pdf
from grpop.provenance import validate_observations
from grpop.snapshots import Snapshot

SNAP = Snapshot(
    "0" * 64, elstat_pdf.SOURCE_ID, "https://example.org/x", datetime(2026, 10, 6, tzinfo=UTC), 1
)
PAGE1 = "ΕΛΛΗΝΙΚΗ ΔΗΜΟΚΡΑΤΙΑ\nΠειραιάς, 1 Οκτωβρίου 2026\nΣΤΟΙΧΕΙΑ ΦΥΣΙΚΗΣ ΚΙΝΗΣΗΣ ΠΛΗΘΥΣΜΟΥ: 2025"  # noqa: RUF001
TABLE1 = """Πίνακας 1. Γεννήσεις ζώντων και Θάνατοι
Γεννήσεις Θάνατοι Φυσική Μεταβολή
1932 185.523 117.593 67.930
2023 71.455 128.097* -56.642
2024 1.000 1.200 -200
2025 {births} {deaths} {change}
* Τα στοιχεία έχουν αναθεωρηθεί κατόπιν δημοσίευσης
Γράφημα 1."""  # noqa: RUF001


def _num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def table2(change: dict[str, tuple[int, int]] | None = None) -> tuple[str, int, int]:
    """Table 2 from the reference labels: each unit i gets i+10 births and 2i+20 deaths,
    regions their units' sum (Attica 500 and 900), abroad 7 and 30."""
    areas = pl.read_csv(REFERENCE / "elstat_areas_el.csv", schema_overrides={"geo_code": pl.String})
    counts: dict[str, tuple[int, int]] = {"Εξωτερικό": (7, 30), "Αττική": (500, 900)}
    units = areas.filter(pl.col("geo_code").str.len_chars() == 5)
    for i, label in enumerate(units["label_el"]):
        counts[label] = (i + 10, 2 * i + 20)
    for region in areas.filter(pl.col("geo_code").str.len_chars() == 4).iter_rows(named=True):
        children = units.filter(pl.col("geo_code").str.head(4) == region["geo_code"])["label_el"]
        if len(children):
            counts[region["label_el"]] = (
                sum(counts[c][0] for c in children),
                sum(counts[c][1] for c in children),
            )
    regions = [lbl for lbl, code in areas.iter_rows() if code is None or len(code) == 4]
    total = (sum(counts[r][0] for r in regions), sum(counts[r][1] for r in regions))
    counts["ΣΥΝΟΛΟ ΧΩΡΑΣ"] = total
    counts.update(change or {})
    lines = [
        f"{lbl} {_num(counts[lbl][0])} -4,2% {_num(counts[lbl][1])} 0,1%"
        for lbl in areas["label_el"]
    ]
    head = (
        "Πίνακας 2. Γεννήσεις ζώντων και Θάνατοι κατά τόπο μόνιμης κατοικίας\n"
        "μητέρας/θανόντα, έτους 2025, και μεταβολές (%) 2025/2024\n"
    )
    return head + "\n".join(lines), *total


def pdf_text(change: dict[str, tuple[int, int]] | None = None, table1: str = TABLE1) -> list[str]:
    t2, births, deaths = table2(change)
    return [
        PAGE1,
        table1.format(births=_num(births), deaths=_num(deaths), change=_num(births - deaths)),
        t2,
    ]


@pytest.fixture
def observations(monkeypatch):
    def run(text: list[str]) -> pl.DataFrame:
        monkeypatch.setattr(elstat_pdf, "pages", lambda _: text)
        return validate_observations(elstat_pdf.to_observations(SNAP, b"%PDF"))

    return run


def test_national_series_regions_and_merged_nuts3(observations):
    df = observations(pdf_text())

    def at(definition: str, geo: str, period: str) -> pl.DataFrame:
        return df.filter(
            (pl.col("definition_id") == definition)
            & (pl.col("geo_code") == geo)
            & (pl.col("period") == period)
        )

    assert at("deaths@v1", "EL", "2023")["status"].item() == "revised"
    assert at("natural_change@v1", "EL", "2023")["status"].item() == "revised"
    assert at("live_births@v1", "EL", "2023")["status"].item() == "final"
    assert set(df["vintage"]) == {"2026-10-01"}
    # Γρεβενά and Κοζάνη are one NUTS 3 region: their sum, derived
    assert at("live_births@v1", "EL531", "2025")["nature"].item() == "derived"
    assert at("live_births@v1", "EL532", "2025")["nature"].item() == "observed"
    # Attica as a whole, its NUTS 3 regions not given; abroad not published
    assert at("deaths@v1", "EL30", "2025")["value"].item() == 900
    assert not df.filter(
        pl.col("geo_code").str.starts_with("EL30") & (pl.col("geo_code") != "EL30")
    ).height
    assert df.filter(pl.col("period") == "2025")["geo_code"].n_unique() == 1 + 13 + 45
    assert set(df.filter(pl.col("period") == "1932")["definition_id"]) == {
        "live_births@v1",
        "deaths@v1",
        "natural_change@v1",
    }


def test_a_release_that_does_not_add_up_stops(observations):
    with pytest.raises(ValueError, match="regional units do not add up"):
        observations(pdf_text({"Χίος": (1, 1)}))
    with pytest.raises(ValueError, match="regions and abroad"):
        observations(pdf_text({"Εξωτερικό": (8, 30)}))
    with pytest.raises(ValueError, match="births minus deaths"):
        observations(pdf_text(table1=TABLE1.replace("1.200 -200", "1.200 -201")))
    with pytest.raises(ValueError, match="country row differs from Table 1"):
        observations(pdf_text(table1=TABLE1.replace("{births} {deaths} {change}", "1 2 -1")))


def test_reference_labels_are_greek_nuts_2024_codes():
    areas = pl.read_csv(REFERENCE / "elstat_areas_el.csv", schema_overrides={"geo_code": pl.String})
    nuts = set(pl.read_csv(REFERENCE / "nuts2024_el.csv")["geo_code"])
    assert set(areas["geo_code"].drop_nulls()) <= nuts
    assert areas["label_el"].is_unique().all()


def test_the_recorded_2025_release():
    raw = (Path(__file__).parent / "fixtures" / "elstat_spo03_2025.pdf").read_bytes()
    snap = Snapshot(
        hashlib.sha256(raw).hexdigest(),
        elstat_pdf.SOURCE_ID,
        "https://example.org/x",
        SNAP.retrieved_at,
        len(raw),
    )
    df = validate_observations(elstat_pdf.to_observations(snap, raw))
    value = dict(
        zip(
            df["definition_id"] + " " + df["geo_code"] + " " + df["period"],
            df["value"],
            strict=True,
        )
    )
    assert value["natural_change@v1 EL 2025"] == -56223
    assert value["live_births@v1 EL 2025"] == 65618
    assert value["deaths@v1 EL30 2025"] == 40879
    assert value["live_births@v1 EL531 2025"] == 719 + 109  # Κοζάνη + Γρεβενά
    assert (df.height, set(df["vintage"])) == (188, {"2026-10-01"})
