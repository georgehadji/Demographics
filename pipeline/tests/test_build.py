"""The build on a store of the recorded responses (test_indicators.RECORDED)."""

import dataclasses
import json
import shutil
from datetime import UTC, datetime

import polars as pl
import pytest
from test_indicators import FIXTURES, RECORDED

from grpop import build, indicators, snapshots
from grpop.provenance import validate_observations


@pytest.fixture(scope="module", autouse=True)
def steps():
    """A few steps of each kind; tests/test_indicators.py covers each step's output."""
    names = [
        "old_age_dependency_ratio",
        "median_age",
        "net_migration",
        "population_regional",
        "geometry_el_nuts2",
    ]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(build, "STEPS", {name: build.STEPS[name] for name in names})
        yield


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    root = tmp_path_factory.mktemp("store")
    # The GISCO fixture is hand-written (see its _comment).
    files = {**RECORDED, "gisco_nuts2_2024_geo": "gisco_nuts2_handwritten.geojson"}
    for source_id, fixture in files.items():
        snapshots.put(
            root,
            (FIXTURES / fixture).read_bytes(),
            source_id=source_id,
            source_url="https://example.org/x",
            retrieved_at=datetime(2026, 9, 29, tzinfo=UTC),
        )
    return root


@pytest.fixture(scope="module")
def product(store, tmp_path_factory):
    out = tmp_path_factory.mktemp("product")
    assert build.build(store, out) == list(build.STEPS)
    return out


def test_two_builds_from_scratch_give_the_same_bytes(store, product, tmp_path):
    build.build(store, tmp_path)
    files = {p.name for p in product.iterdir()}
    assert files == {p.name for p in tmp_path.iterdir()}
    for name in files:
        assert (product / name).read_bytes() == (tmp_path / name).read_bytes(), name


def test_every_file_is_in_the_manifest_and_every_value_passes_the_contract(product):
    manifest = json.loads((product / "manifest.json").read_bytes())
    listed = {f for entry in manifest.values() for f in entry["files"]}
    assert listed | {"manifest.json"} == {p.name for p in product.iterdir()}
    for name, entry in manifest.items():
        if name in build.GEOMETRY:
            doc = json.loads((product / f"{name}.geojson").read_bytes())
            assert len(doc["features"]) == entry["rows"] > 0
            assert doc["attribution"]
        else:
            df = validate_observations(pl.read_parquet(product / f"{name}.parquet"))
            assert df.height == entry["rows"] > 0
        assert {s["source_id"] for s in entry["sources"]} == build.STEPS[name].sources


def test_only_changed_outputs_are_rebuilt(store, product, tmp_path):
    shutil.copytree(product, tmp_path, dirs_exist_ok=True)
    assert build.build(store, tmp_path) == []
    (tmp_path / "median_age.csv").write_text("edited")
    assert build.build(store, tmp_path) == ["median_age"]
    assert (tmp_path / "median_age.csv").read_bytes() == (product / "median_age.csv").read_bytes()


IND = indicators.INDICATORS["old_age_dependency_ratio"]


@pytest.mark.parametrize(
    "changed",
    [
        # a difference that is neither listed nor corroborated
        {"formula": lambda i: IND.formula(i).with_columns(value=pl.col("value") + 0.1)},
        # a listed difference that is not there
        {"known_differences": frozenset({("EL", "2024")})},
    ],
)
def test_unexplained_or_stale_difference_stops_the_build(store, tmp_path, monkeypatch, changed):
    step = build._indicator(dataclasses.replace(IND, **changed))
    monkeypatch.setattr(build, "STEPS", {"old_age_dependency_ratio": step})
    with pytest.raises(ValueError, match="differences from the official value"):
        build.build(store, tmp_path)
