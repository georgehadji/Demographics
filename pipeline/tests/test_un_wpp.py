"""UN WPP 2024 PPP/POPTOT on the published workbook (recorded 2026-10-03)."""

import hashlib
from datetime import UTC, datetime

import polars as pl
import pytest
from test_indicators import FIXTURES, data

from grpop import projections
from grpop.indicators import SERIES
from grpop.parse import un_wpp
from grpop.provenance import validate_observations
from grpop.snapshots import Snapshot

RAW = (FIXTURES / "un_wpp2024_ppp_poptot.xlsx").read_bytes()
SNAP = Snapshot(
    hashlib.sha256(RAW).hexdigest(),
    un_wpp.SOURCE_ID,
    "https://example.org/x",
    datetime(2026, 10, 3, tzinfo=UTC),
    len(RAW),
)


@pytest.fixture(scope="module")
def wpp():
    return validate_observations(un_wpp.to_observations(SNAP, RAW, {"EL", "CY", "PL"}))


def test_median_and_bounds_of_greece(wpp):
    el = wpp.filter((pl.col("geo_code") == "EL") & (pl.col("period") == "2024"))
    by = dict(zip(el["interval"].fill_null("median"), el["value"], strict=True))
    assert by["median"] == 10047817  # 10047.817 thousand in the workbook
    assert by["95_lower"] <= by["80_lower"] <= by["median"] <= by["80_upper"] <= by["95_upper"]
    assert set(wpp["geo_code"]) == {"EL", "CY", "PL"}  # GR -> EL
    assert (wpp["period"].min(), wpp["period"].max()) == ("2024", "2100")


def test_check_against_the_observed_population(wpp, monkeypatch):
    observed = SERIES["population"].read(data(["eurostat_demo_pjan"]))  # EL and CY
    assert projections.wpp_checked(wpp, observed) is wpp
    monkeypatch.setattr(projections, "WPP_KNOWN_DIFFERENCES", frozenset())
    with pytest.raises(ValueError, match=r"off \['CY'\]"):
        projections.wpp_checked(wpp, observed)
    monkeypatch.setattr(projections, "WPP_KNOWN_DIFFERENCES", frozenset({"CY", "EL"}))
    with pytest.raises(ValueError, match=r"gone \['EL'\]"):
        projections.wpp_checked(wpp, observed)
