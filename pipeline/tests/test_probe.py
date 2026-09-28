import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from grpop.sources.probe import probe_entry, render_markdown
from grpop.sources.registry import SourceEntry

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "jsonstat_sparse.json").read_text(encoding="utf-8")
)


def entry(kind: str) -> SourceEntry:
    return SourceEntry(
        id="e",
        provider="P",
        dataset_code="c",
        title="t",
        access="api",
        probe_kind=kind,
        probe_url="https://example.org/data",
        licence="to_verify",
        licence_key="to_verify",
        used_for=["a"],
        phase=1,
        verification={"status": "unverified"},
    )


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_jsonstat_probe_ok():
    result = probe_entry(
        entry("eurostat_jsonstat"), client(lambda r: httpx.Response(200, json=FIXTURE))
    )
    assert result.ok
    assert json.loads(result.detail)["n_values"] == 7


def test_jsonstat_probe_rejects_non_jsonstat():
    result = probe_entry(
        entry("eurostat_jsonstat"), client(lambda r: httpx.Response(200, text="<html>"))
    )
    assert not result.ok


def test_http_error_status_fails():
    result = probe_entry(entry("http"), client(lambda r: httpx.Response(404, text="nope")))
    assert not result.ok and result.http_status == 404


def test_network_error_is_reported_not_raised():
    def boom(request):
        raise httpx.ConnectError("blocked")

    result = probe_entry(entry("http"), client(boom))
    assert not result.ok and result.http_status is None


def test_markdown_report_escapes_pipes():
    result = probe_entry(entry("http"), client(lambda r: httpx.Response(500, text="a|b")))
    report = render_markdown([result], datetime(2026, 1, 1, tzinfo=UTC))
    assert "a\\|b" in report
    assert "0 of 1 sources OK" in report
