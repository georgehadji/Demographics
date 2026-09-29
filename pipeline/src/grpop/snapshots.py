"""Raw source files, stored once by content (ADR 0005, layer L1).

``objects/<sha256>`` holds the bytes. ``manifest.jsonl`` records, append-only, which
source each object came from and when it was retrieved. A revision is a new object
plus a new manifest line, so a source's history is its lines in order. Nothing is
overwritten or deleted.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from grpop.sources.registry import get_source


@dataclass(frozen=True)
class Snapshot:
    sha256: str
    source_id: str
    source_url: str
    retrieved_at: datetime
    size: int


def read(root: Path, sha256: str) -> bytes:
    """Bytes of one object. Raises ``ValueError`` if they no longer match the hash."""
    data = (root / "objects" / sha256).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError(f"snapshot {sha256} is corrupt")
    return data


def history(root: Path, source_id: str) -> list[Snapshot]:
    """Every snapshot of one source, oldest first."""
    manifest = root / "manifest.jsonl"
    if not manifest.exists():
        return []
    out = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec["source_id"] == source_id:
            out.append(
                Snapshot(**rec | {"retrieved_at": datetime.fromisoformat(rec["retrieved_at"])})
            )
    return out


def put(
    root: Path, data: bytes, *, source_id: str, source_url: str, retrieved_at: datetime
) -> Snapshot:
    """Store one download of a registry source and return its snapshot.

    If the content equals the source's latest snapshot, nothing is written and that
    snapshot is returned.
    """
    if retrieved_at.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    get_source(source_id)  # only registry sources are stored
    sha256 = hashlib.sha256(data).hexdigest()
    past = history(root, source_id)
    if past and past[-1].sha256 == sha256:
        return past[-1]

    path = root / "objects" / sha256
    if path.exists():
        read(root, sha256)  # same content from an earlier download; must still be intact
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)

    # The object is written before its manifest line, so no line points at a missing object.
    snap = Snapshot(sha256, source_id, source_url, retrieved_at.astimezone(UTC), len(data))
    with (root / "manifest.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(snap) | {"retrieved_at": snap.retrieved_at.isoformat()}) + "\n")
    return snap
