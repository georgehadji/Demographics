"""Eurostat connector: download whole datasets into the snapshot store (ADR 0005, L1).

Only bytes are fetched and stored; parsing happens in ``grpop.parse``. The download
URL is the registry's probe URL without its filters, i.e. the whole dataset as
JSON-stat. Registry entries with ``ingest`` set (e.g. GISCO boundaries) are files
stored as they are, from their probe URL. Run by the Ingest workflow, which keeps the
store as release assets.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from grpop import snapshots
from grpop.parse import jsonstat
from grpop.sources.probe import USER_AGENT
from grpop.sources.registry import SourceEntry, load_registry

RETRY_STATUS = {429, 500, 502, 503, 504}


def dataset_url(entry: SourceEntry) -> str:
    if entry.ingest:
        return entry.probe_url
    return entry.probe_url.split("?")[0] + "?format=JSON&lang=EN"


def _check(entry: SourceEntry, data: bytes) -> None:
    doc = json.loads(data)
    if entry.ingest == "geojson":
        if doc.get("type") != "FeatureCollection" or not doc.get("features"):
            raise ValueError(f"{entry.id}: response is not a non-empty GeoJSON FeatureCollection")
    elif doc.get("class") != "dataset" or jsonstat.summarize(doc)["n_values"] == 0:
        raise ValueError(f"{entry.id}: response is not a non-empty JSON-stat dataset")


def fetch(client: httpx.Client, url: str, *, attempts: int = 4, backoff: float = 5.0) -> bytes:
    """GET with exponential backoff on network errors, 429 and 5xx."""
    for attempt in range(attempts):
        if attempt:
            time.sleep(backoff * 2 ** (attempt - 1))
        last = attempt == attempts - 1
        try:
            response = client.get(url)
        except httpx.TransportError:
            if last:
                raise
            continue
        if response.status_code in RETRY_STATUS and not last:
            continue
        response.raise_for_status()
        return response.content
    raise AssertionError("unreachable")


def ingest(
    root: Path, entries: list[SourceEntry], client: httpx.Client, *, backoff: float = 5.0
) -> list[snapshots.Snapshot]:
    """Download each entry's whole dataset and store it. Fails on the first bad response."""
    out = []
    for entry in entries:
        url = dataset_url(entry)
        data = fetch(client, url, backoff=backoff)
        _check(entry, data)
        out.append(
            snapshots.put(
                root, data, source_id=entry.id, source_url=url, retrieved_at=datetime.now(UTC)
            )
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True, help="snapshot store directory")
    parser.add_argument("--phase", type=int, default=1, help="ingest sources up to this phase")
    args = parser.parse_args(argv)

    entries = [
        e
        for e in load_registry()
        if (e.probe_kind == "eurostat_jsonstat" or e.ingest) and e.phase <= args.phase
    ]
    with httpx.Client(
        timeout=300, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        for snap in ingest(args.store, entries, client):
            print(f"{snap.source_id}\t{snap.sha256[:12]}\t{snap.size}\t{snap.retrieved_at}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
