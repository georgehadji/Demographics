import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from grpop import snapshots
from grpop.parse import eurostat
from grpop.provenance import Nature, validate_observations

FIXTURES = Path(__file__).parent / "fixtures"
# Recorded from the live API: demo_pjan, geo EL and CY, sex T and F, 2023 onwards.
PJAN = (FIXTURES / "eurostat_demo_pjan_el_cy.json").read_bytes()
T = datetime(2026, 9, 29, tzinfo=UTC)


def parse(data, tmp_path, source_id="eurostat_demo_pjan", **kw):
    snap = snapshots.put(
        tmp_path,
        data,
        source_id=source_id,
        source_url="https://example.org/x",
        retrieved_at=T,
    )
    kw = {"definition_id": "population_1jan@v1", "nature": Nature.OFFICIAL_ESTIMATE} | kw
    return eurostat.to_observations(snap, data, geo_vintage="NUTS2024", **kw)


# Every flag found in the six Phase 1 snapshots of 2026-09-29, with its meaning:
# (provisional, estimated, break in series).
@pytest.mark.parametrize(
    ("flag", "meaning"),
    [
        ("", (False, False, False)),
        ("b", (False, False, True)),
        ("e", (False, True, False)),
        ("i", (False, True, False)),
        ("p", (True, False, False)),
        ("be", (False, True, True)),
        ("bp", (True, False, True)),
        ("ep", (True, True, False)),
        ("bep", (True, True, True)),
        ("|N", (False, False, False)),
        ("b|N", (False, False, True)),
    ],
)
def test_every_ingested_flag_has_a_meaning(flag, meaning):
    assert eurostat.flag_meaning(flag) == meaning


@pytest.mark.parametrize("flag", ["c", "d", "u", "|C"])
def test_unknown_flag_fails(flag):
    with pytest.raises(ValueError, match="unknown Eurostat flag"):
        eurostat.flag_meaning(flag)


@pytest.mark.parametrize(
    ("code", "age"),
    [
        ("TOTAL", "total"),
        ("UNK", "unknown"),
        ("Y_LT1", "0"),
        ("Y42", "42"),
        ("Y15-19", "15-19"),
        ("Y_GE85", "85+"),
    ],
)
def test_age_codes(code, age):
    assert eurostat.age(code) == age


def test_unknown_age_code_fails():
    with pytest.raises(ValueError, match="unknown Eurostat age"):
        eurostat.age("Y_LT15")


def test_recorded_snapshot_passes_the_contract(tmp_path):
    obs = validate_observations(parse(PJAN, tmp_path))
    assert obs.height == len(json.loads(PJAN)["value"])  # every cell has a value here
    assert not obs["age"].str.starts_with("Y").any()
    el = obs.filter(geo_code="EL", period="2025", sex="total")
    assert "100+" in el["age"].to_list()  # Y_OPEN above the last single year, Y99


def test_flags_become_status_nature_and_break(tmp_path):
    # The recorded extract carries no flags, so flags are set on a copy of it.
    doc = json.loads(PJAN)
    doc["status"] = {"0": "bp", "1": "e", "2": "|N"}
    del doc["value"]["2"]
    data = json.dumps(doc).encode()
    obs = validate_observations(parse(data, tmp_path, nature=Nature.OBSERVED)).head(3)
    assert obs["status"].to_list() == ["provisional", "final", "not_available"]
    assert obs["break_in_series"].to_list() == [True, False, False]
    assert obs["nature"].to_list() == ["observed", "official_estimate", "observed"]


def test_multi_category_dimension_must_be_selected(tmp_path):
    data = (FIXTURES / "eurostat_demo_find_el.json").read_bytes()
    with pytest.raises(ValueError, match="select a single 'indic_de'"):
        parse(data, tmp_path, source_id="eurostat_demo_find")


def test_data_must_match_snapshot(tmp_path):
    snap = snapshots.put(
        tmp_path,
        PJAN,
        source_id="eurostat_demo_pjan",
        source_url="https://example.org/x",
        retrieved_at=T,
    )
    with pytest.raises(ValueError, match="does not belong"):
        eurostat.to_observations(
            snap,
            PJAN + b" ",
            definition_id="population_1jan@v1",
            nature=Nature.OFFICIAL_ESTIMATE,
            geo_vintage="NUTS2024",
        )
