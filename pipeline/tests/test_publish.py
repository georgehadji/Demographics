"""Data release: packaging, Zenodo deposit (mocked) and pinned snapshots."""

import json
import zipfile

import httpx
import pytest
from test_eurostat import client

from grpop import build, publish, snapshots

MANIFEST = {
    "population": {
        "files": {"population.csv": "a", "population.parquet": "b"},
        "sources": [{"source_id": "eurostat_demo_pjan", "sha256": "1" * 64}],
    },
    "geometry_el_nuts2": {
        "files": {"geometry_el_nuts2.geojson": "c"},
        "sources": [{"source_id": "gisco_nuts2_2024_geo", "sha256": "2" * 64}],
    },
}


@pytest.fixture
def product(tmp_path):
    p = tmp_path / "product"
    p.mkdir()
    (p / "manifest.json").write_text(json.dumps(MANIFEST))
    for entry in MANIFEST.values():
        for f in entry["files"]:
            (p / f).write_bytes(f.encode())
    return p


@pytest.fixture
def changelog(tmp_path, monkeypatch):
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Data releases\n\n## 1.0.0 (2026-10-03)\n\nFirst.\n\n## 0.9.0 (x)\n\nOld.\n")
    monkeypatch.setattr(publish, "CHANGELOG", path)
    return path


def test_the_zip_is_reproducible_and_leaves_out_non_commercial_files(product, changelog, tmp_path):
    a = publish.package(product, "1.0.0", tmp_path)
    first = a.read_bytes()
    assert publish.package(product, "1.0.0", tmp_path).read_bytes() == first
    names = zipfile.ZipFile(a).namelist()
    assert names == sorted(names)
    assert "geometry_el_nuts2.geojson" not in names
    assert {
        "population.csv",
        "manifest.json",
        "SOURCES.md",
        "snapshots.txt",
        "CHANGELOG.md",
    } <= set(names)
    z = zipfile.ZipFile(a)
    assert z.read("snapshots.txt").decode().split() == ["1" * 64, "2" * 64]
    assert z.read("CHANGELOG.md").decode().startswith("## 1.0.0 (2026-10-03)")
    assert "Old." not in z.read("CHANGELOG.md").decode()
    assert "Licence:" in z.read("SOURCES.md").decode()


def test_only_the_newest_changelog_entry_can_be_published(product, changelog, tmp_path):
    with pytest.raises(ValueError, match="newest entry"):
        publish.package(product, "0.9.0", tmp_path)


def test_metadata_come_from_citation_cff():
    m = publish.metadata("1.0.0")
    assert m["upload_type"] == "dataset" and m["license"] == "cc-by-4.0"
    assert m["creators"] == [{"name": "Chatzivantsidis, Georgios-Chrysovalantis"}]
    assert m["title"].endswith("data release 1.0.0")


def _api(new_version: bool):
    api = "https://z.example/api"
    dep = {
        "links": {
            "bucket": f"{api}/files/b",
            "self": f"{api}/deposit/depositions/9",
            "publish": f"{api}/deposit/depositions/9/actions/publish",
        },
        "files": [{"links": {"self": f"{api}/deposit/depositions/9/files/old"}}],
    }
    responses = (
        [
            httpx.Response(200, json={"id": 8}),
            httpx.Response(201, json={"links": {"latest_draft": dep["links"]["self"]}}),
            httpx.Response(200, json=dep),
            httpx.Response(204),
        ]
        if new_version
        else [httpx.Response(201, json=dep)]
    ) + [
        httpx.Response(201, json={}),
        httpx.Response(200, json={}),
        httpx.Response(202, json={"doi": "10.5281/zenodo.123"}),
    ]
    return api, responses


@pytest.mark.parametrize("concept", [None, "7"])
def test_deposit_uploads_describes_and_publishes(product, changelog, tmp_path, concept):
    zipped = publish.package(product, "1.0.0", tmp_path)
    api, responses = _api(new_version=bool(concept))
    c, seen = client(responses)
    assert publish.deposit(c, api, zipped, "1.0.0", concept) == "10.5281/zenodo.123"
    calls = [(r.method, str(r.url)) for r in seen]
    assert ("PUT", f"{api}/files/b/{zipped.name}") in calls
    assert calls[-1] == ("POST", f"{api}/deposit/depositions/9/actions/publish")
    if concept:
        assert calls[:2] == [
            ("GET", f"{api}/records/7"),
            ("POST", f"{api}/deposit/depositions/8/actions/newversion"),
        ]
        assert ("DELETE", f"{api}/deposit/depositions/9/files/old") in calls


def test_pin_builds_from_the_listed_snapshots(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    monkeypatch.setattr(
        build, "STEPS", {"x": build.Step(frozenset({"eurostat_demo_pjan"}), lambda d: d)}
    )
    old, new = (
        snapshots.put(
            tmp_path,
            data,
            source_id="eurostat_demo_pjan",
            source_url="https://e.org",
            retrieved_at=t,
        )
        for data, t in (
            (b"old", datetime(2026, 1, 1, tzinfo=UTC)),
            (b"new", datetime(2026, 2, 1, tzinfo=UTC)),
        )
    )
    assert build.latest(tmp_path)["eurostat_demo_pjan"].sha256 == new.sha256
    assert build.latest(tmp_path, {old.sha256})["eurostat_demo_pjan"].sha256 == old.sha256
