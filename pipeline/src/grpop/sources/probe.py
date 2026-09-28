"""Check every registry entry against the live source and write a report.

The report is evidence for updating ``verification`` in registry.yaml. The probe
never edits the registry itself: a person or a Claude session reads the report
and records the evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from grpop.sources import jsonstat
from grpop.sources.registry import SourceEntry, load_registry

USER_AGENT = "grpop-source-probe (non-commercial research; github.com/georgehadji/Demographics)"


@dataclass
class ProbeResult:
    id: str
    url: str
    ok: bool
    http_status: int | None
    content_type: str | None
    bytes: int | None
    detail: str


def probe_entry(entry: SourceEntry, client: httpx.Client) -> ProbeResult:
    try:
        response = client.get(entry.probe_url)
    except httpx.HTTPError as exc:
        return ProbeResult(entry.id, entry.probe_url, False, None, None, None, repr(exc))

    ctype = response.headers.get("content-type")
    base = dict(
        id=entry.id,
        url=entry.probe_url,
        http_status=response.status_code,
        content_type=ctype,
        bytes=len(response.content),
    )
    if response.status_code != 200:
        return ProbeResult(ok=False, detail=response.text[:300], **base)

    if entry.probe_kind == "eurostat_jsonstat":
        try:
            summary = jsonstat.summarize(response.json())
        except (ValueError, KeyError, TypeError) as exc:
            return ProbeResult(ok=False, detail=f"not JSON-stat: {exc!r}", **base)
        return ProbeResult(ok=summary["n_values"] > 0, detail=json.dumps(summary), **base)

    return ProbeResult(ok=True, detail="reachable", **base)


def render_markdown(results: list[ProbeResult], started: datetime) -> str:
    lines = [
        f"# Source probe report ({started.isoformat(timespec='seconds')})",
        "",
        f"{sum(r.ok for r in results)} of {len(results)} sources OK.",
        "",
        "| id | ok | HTTP | type | bytes | detail |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        detail = r.detail.replace("|", "\\|").replace("\n", " ")[:400]
        lines.append(
            f"| `{r.id}` | {'yes' if r.ok else '**no**'} | {r.http_status} | "
            f"{r.content_type} | {r.bytes} | {detail} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("probe-report.md"))
    parser.add_argument("--json", type=Path, default=Path("probe-report.json"))
    parser.add_argument("--strict", action="store_true", help="exit 1 if any source fails")
    args = parser.parse_args(argv)

    started = datetime.now(UTC)
    with httpx.Client(
        timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        results = [probe_entry(e, client) for e in load_registry()]

    args.report.write_text(render_markdown(results, started), encoding="utf-8")
    args.json.write_text(
        json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(args.report.read_text(encoding="utf-8"))
    return 1 if args.strict and not all(r.ok for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
