"""The data product (ADR 0005, layers L4-L5): ``grpop-build --store DIR --out DIR``.

The build is a function of the latest snapshot of each source, the code and the
reference data. Its DAG is explicit: each entry of ``STEPS`` is one indicator or
official series and the sources it reads. An indicator that differs from its official
counterpart without explanation (``indicators.check``) stops the build. Every output is
validated, written as Parquet and CSV with its rows in key order, and listed in
``manifest.json`` with the sha256 of each file, its sources and the hash of its inputs
(snapshots, code, reference data). An output whose inputs are unchanged and whose files
are intact is not rebuilt. Two builds from the same inputs give the same bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from grpop import harmonize, indicators, snapshots
from grpop.provenance import OBSERVATION_KEY, ObservationSchema, validate_observations
from grpop.snapshots import Snapshot

COLUMNS = list(ObservationSchema.to_schema().columns)


@dataclass(frozen=True)
class Step:
    sources: frozenset[str]
    run: Callable[[indicators.Data], pl.DataFrame]


def _indicator(indicator: indicators.Indicator) -> Step:
    def run(data: indicators.Data) -> pl.DataFrame:
        ours = indicators.compute(indicator, data)
        if indicator.official:
            unexplained, gone = indicators.check(indicator, ours, data)
            if unexplained.height or gone:
                with pl.Config(tbl_rows=-1):
                    raise ValueError(
                        f"{indicator.definition_id}: differences from the official value "
                        f"that are neither listed nor corroborated:\n{unexplained}\n"
                        f"listed differences that are gone or now corroborated: {gone}"
                    )
        return ours

    return Step(frozenset(indicators.sources(indicator)), run)


def _series(series: indicators.Series) -> Step:
    return Step(frozenset({series.source_id}), series.read)


if indicators.INDICATORS.keys() & indicators.SERIES.keys():
    raise ValueError("an indicator and a series share a name")
STEPS = {
    **{name: _indicator(i) for name, i in indicators.INDICATORS.items()},
    **{name: _series(s) for name, s in indicators.SERIES.items()},
}


def latest(store: Path) -> dict[str, Snapshot]:
    """The latest snapshot of every source the build reads."""
    out = {}
    for source_id in sorted(set().union(*(step.sources for step in STEPS.values()))):
        history = snapshots.history(store, source_id)
        if not history:
            raise ValueError(f"no snapshot of {source_id} in {store}")
        out[source_id] = history[-1]
    return out


def _code_hash() -> str:
    """Code, reference data and the Polars version that writes the files."""
    h = hashlib.sha256(pl.__version__.encode())
    package = Path(__file__).parent
    files = [*package.rglob("*.py"), *package.rglob("*.yaml"), *harmonize.REFERENCE.rglob("*")]
    for path in sorted((p for p in files if p.is_file()), key=Path.as_posix):
        h.update(path.read_bytes().replace(b"\r\n", b"\n"))  # same hash on Windows checkouts
    return h.hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(df: pl.DataFrame, out: Path, name: str) -> dict[str, str]:
    df = validate_observations(df.select(COLUMNS).sort(OBSERVATION_KEY, nulls_last=True))
    df.write_parquet(out / f"{name}.parquet")
    df.write_csv(out / f"{name}.csv")
    return {f: _sha256(out / f) for f in (f"{name}.parquet", f"{name}.csv")}


def build(store: Path, out: Path) -> list[str]:
    """Build every step into ``out``; returns the names of the steps that were rebuilt."""
    snaps, code = latest(store), _code_hash()
    manifest_path = out / "manifest.json"
    old = json.loads(manifest_path.read_bytes()) if manifest_path.exists() else {}
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {}
    rebuilt = []
    try:
        for name, step in STEPS.items():
            used = [snaps[s] for s in sorted(step.sources)]
            # retrieved_at and source_url are in the output rows, so they are inputs too.
            sources = [
                {
                    "source_id": s.source_id,
                    "sha256": s.sha256,
                    "source_url": s.source_url,
                    "retrieved_at": s.retrieved_at.isoformat(),
                }
                for s in used
            ]
            inputs = hashlib.sha256(json.dumps([code, sources]).encode()).hexdigest()
            entry = old.get(name)
            if not (
                entry
                and entry["inputs"] == inputs
                and all(
                    (out / f).exists() and _sha256(out / f) == h for f, h in entry["files"].items()
                )
            ):
                df = step.run({s.source_id: (s, snapshots.read(store, s.sha256)) for s in used})
                files = _write(df, out, name)
                entry = {"inputs": inputs, "rows": df.height, "sources": sources, "files": files}
                rebuilt.append(name)
                print(f"{name}: {df.height} rows", flush=True)
            manifest[name] = entry
    finally:
        # Also after a failed step, so the manifest matches the files already rewritten.
        # Steps not reached keep their old entries. Files of removed steps stay, unlisted.
        current = {n: manifest.get(n) or old.get(n) for n in STEPS}
        text = json.dumps({n: e for n, e in current.items() if e}, indent=1, sort_keys=True)
        manifest_path.write_bytes((text + "\n").encode())
    return rebuilt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1] if __doc__ else None)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--list-snapshots",
        action="store_true",
        help="print the sha256 of every snapshot the build reads, and exit",
    )
    args = parser.parse_args(argv)
    if args.out is None and not args.list_snapshots:
        parser.error("--out is required")
    try:
        if args.list_snapshots:
            print("\n".join(sorted({s.sha256 for s in latest(args.store).values()})))
        else:
            build(args.store, args.out)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    return 0
