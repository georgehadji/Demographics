from pathlib import Path

import httpx
import pytest

from grpop import snapshots
from grpop.sources import eurostat
from grpop.sources.registry import get_source

# Recorded from the live API (demo_find, geo=EL, latest year), not hand-written.
RECORDED = (Path(__file__).parent / "fixtures" / "eurostat_demo_find_el.json").read_bytes()
ENTRY = get_source("eurostat_demo_find")


def client(responses):
    """Mock client that serves the given responses in order and records requests."""
    seen = []

    def handler(request):
        seen.append(request)
        r = responses[len(seen) - 1]
        if isinstance(r, Exception):
            raise r
        return r

    c = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": "ua"})
    return c, seen


def test_download_url_is_whole_dataset():
    url = eurostat.dataset_url(ENTRY)
    assert url.endswith("/demo_find?format=JSON&lang=EN")
    assert "geo=" not in url


def test_retries_network_errors_and_5xx_then_succeeds():
    c, seen = client(
        [httpx.ConnectError("down"), httpx.Response(503), httpx.Response(200, content=b"ok")]
    )
    assert eurostat.fetch(c, "https://x", backoff=0) == b"ok"
    assert len(seen) == 3


def test_gives_up_after_last_attempt_and_does_not_retry_4xx():
    c, seen = client([httpx.Response(503)] * 4)
    with pytest.raises(httpx.HTTPStatusError):
        eurostat.fetch(c, "https://x", backoff=0)
    assert len(seen) == 4
    c, seen = client([httpx.Response(404)])
    with pytest.raises(httpx.HTTPStatusError):
        eurostat.fetch(c, "https://x", backoff=0)
    assert len(seen) == 1


def test_ingest_stores_recorded_response_once(tmp_path):
    c, seen = client([httpx.Response(200, content=RECORDED)] * 2)
    [first] = eurostat.ingest(tmp_path, [ENTRY], c, backoff=0)
    [second] = eurostat.ingest(tmp_path, [ENTRY], c, backoff=0)
    assert second == first
    assert snapshots.read(tmp_path, first.sha256) == RECORDED
    assert first.source_url == eurostat.dataset_url(ENTRY) == str(seen[0].url)
    assert len(snapshots.history(tmp_path, ENTRY.id)) == 1


def test_ingest_refuses_non_dataset(tmp_path):
    c, _ = client([httpx.Response(200, json={"class": "error"})])
    with pytest.raises(ValueError, match="not a non-empty JSON-stat dataset"):
        eurostat.ingest(tmp_path, [ENTRY], c, backoff=0)
    assert not (tmp_path / "manifest.jsonl").exists()


GEO = get_source("gisco_nuts2_2024_geo")
# Hand-written, not GISCO data (see the fixture's _comment).
GEOJSON = (Path(__file__).parent / "fixtures" / "gisco_nuts2_handwritten.geojson").read_bytes()


def test_ingest_stores_a_file_entry_from_its_probe_url(tmp_path):
    c, seen = client([httpx.Response(200, content=GEOJSON)])
    [snap] = eurostat.ingest(tmp_path, [GEO], c, backoff=0)
    assert str(seen[0].url) == GEO.probe_url == snap.source_url
    assert snapshots.read(tmp_path, snap.sha256) == GEOJSON


def test_ingest_refuses_a_file_that_is_not_geojson(tmp_path):
    c, _ = client([httpx.Response(200, json={"type": "Feature"})])
    with pytest.raises(ValueError, match="not a non-empty GeoJSON FeatureCollection"):
        eurostat.ingest(tmp_path, [GEO], c, backoff=0)


def test_ingest_refuses_a_file_that_is_not_xlsx(tmp_path):
    c, _ = client([httpx.Response(200, content=b"<html>not found</html>")])
    with pytest.raises(ValueError, match="not an xlsx file"):
        eurostat.ingest(tmp_path, [get_source("un_wpp_2024_ppp_poptot")], c, backoff=0)


def test_ingest_refuses_a_file_that_is_not_pdf(tmp_path):
    c, _ = client([httpx.Response(200, content=b"<html>not found</html>")])
    with pytest.raises(ValueError, match="not a PDF file"):
        eurostat.ingest(tmp_path, [get_source("elstat_spo03_2025")], c, backoff=0)
