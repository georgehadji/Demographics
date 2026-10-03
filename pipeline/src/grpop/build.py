"""The data product (ADR 0005, layers L4-L5): ``grpop-build --store DIR --out DIR``.

The build is a function of the latest snapshot of each source, the code and the
reference data. Its DAG is explicit: each entry of ``STEPS`` is one indicator or
official series and the sources it reads. An indicator that differs from its official
counterpart without explanation (``indicators.check``) stops the build. Every output is
validated, written as Parquet and CSV with its rows in key order, and listed in
``manifest.json`` with the sha256 of each file, its sources and the hash of its inputs
(snapshots, code, reference data). An output whose inputs are unchanged and whose files
are intact is not rebuilt. Two builds from the same inputs give the same bytes. Map
geometry (``GEOMETRY``) is written as GeoJSON with its licence inside: it is not under
CC BY (LICENSE-CONTENT.md).
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

from grpop import groups, harmonize, indicators, projections, snapshots
from grpop.definitions import get_definition
from grpop.parse import gisco, un_wpp
from grpop.provenance import OBSERVATION_KEY, ObservationSchema, validate_observations
from grpop.snapshots import Snapshot

COLUMNS = list(ObservationSchema.to_schema().columns)


@dataclass(frozen=True)
class Step:
    sources: frozenset[str]
    run: Callable[[indicators.Data], pl.DataFrame | dict[str, Any]]  # observations or GeoJSON


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


def _with_median(step: Step) -> Step:
    def run(data: indicators.Data) -> pl.DataFrame:
        df = step.run(data)
        assert isinstance(df, pl.DataFrame)
        return groups.with_median(df)

    return Step(step.sources, run)


def _adds_up(step: Step) -> Step:
    """Stops the build where ages do not add up to the total or regions to their parent,
    beyond the bounds in ``KNOWN_GAPS``. A listed (period, sex) with no gap left also
    stops it, if it was compared."""

    def run(data: indicators.Data) -> pl.DataFrame:
        df = step.run(data)
        assert isinstance(df, pl.DataFrame)
        known = pl.DataFrame(
            [(p, s, b) for (p, s), b in KNOWN_GAPS.items()],
            schema=["period", "sex", "bound"],
            orient="row",
        )
        ages = harmonize.age_gaps(df).with_columns(off=pl.col("total") - pl.col("sum"))
        regions = harmonize.hierarchy_gaps(df)
        regions = regions.with_columns(off=pl.col("value") - pl.col("children"))
        found = set(pl.concat([g.select("period", "sex") for g in (ages, regions)]).iter_rows())
        gone = (set(KNOWN_GAPS) & set(df.select("period", "sex").iter_rows())) - found
        for name, gaps in (("age_gaps", ages), ("hierarchy_gaps", regions)):
            gaps = gaps.join(known, on=["period", "sex"], how="left").filter(
                pl.col("bound").is_null() | (pl.col("off").abs() > pl.col("bound"))
            )
            if gaps.height or gone:
                with pl.Config(tbl_rows=20):
                    raise ValueError(f"{name}:\n{gaps}\nlisted gaps that are gone: {sorted(gone)}")
        return df

    return Step(step.sources, run)


ADDS_UP = {"population_by_age_group_regional"}
# demo_r_pjangrp3 (updated 2026-08-28), 2018, total and female: in 19 cells the age
# groups or the regions add up to 3 persons more or less than the published value
# (e.g. EL645 total 37,978, its age groups 37,975; EL 85-89 242,204, its regions
# 242,207). VERIFIED 2026-10-03 that the regional totals equal demo_r_pjanaggr3 and male
# + female. Cause UNKNOWN. (period, sex) -> the largest difference allowed, in persons.
KNOWN_GAPS = {("2018", "total"): 3, ("2018", "female"): 3}
# National rates and means get the EU-27 median as a comparator; counts do not.
_national = {
    **{n: i.definition_id for n, i in indicators.INDICATORS.items()},
    **{n: s.definition_id for n, s in indicators.SERIES.items()},
}
MEDIAN = {
    n
    for n, d in _national.items()
    if not n.endswith("_regional") and get_definition(d).unit != "persons"
}
_POPULATION, _FERTILITY = (
    indicators.SERIES["population"],
    indicators.INDICATORS["total_fertility_rate"].official[0],
)
PEER_GROUPS = Step(
    frozenset({_POPULATION.source_id, _FERTILITY.source_id}),
    lambda data: groups.check(_POPULATION.read(data), _FERTILITY.read(data)),
)
GEOMETRY = {
    "geometry_el_nuts2": Step(
        frozenset({"gisco_nuts2_2024_geo"}),
        lambda data: gisco.greek_regions(*data["gisco_nuts2_2024_geo"], level=2),
    ),
}
# EUROPOP2025 (ADR 0008): Greece in full detail; totals of every area, whose baseline
# is checked against the observed population in its base year.
PROJECTIONS = {
    "population_projection": Step(
        frozenset({projections.SOURCE}),
        lambda data: projections.read(data).filter(pl.col("geo_code") == "EL"),
    ),
    # UN WPP 2024, Greece and every peer group member, checked against demo_pjan.
    "population_projection_wpp": Step(
        frozenset({un_wpp.SOURCE_ID, _POPULATION.source_id}),
        lambda data: projections.wpp_checked(
            un_wpp.to_observations(*data[un_wpp.SOURCE_ID], set(groups.GROUPS["geo_code"])),
            _POPULATION.read(data),
        ),
    ),
    "population_projection_totals": Step(
        frozenset({projections.SOURCE, _POPULATION.source_id}),
        lambda data: projections.totals(projections.read(data), _POPULATION.read(data)),
    ),
}
_STEPS = {
    **{name: _indicator(i) for name, i in indicators.INDICATORS.items()},
    **{name: _series(s) for name, s in indicators.SERIES.items()},
    **GEOMETRY,
    "peer_groups": PEER_GROUPS,
    **PROJECTIONS,
}
STEPS = {
    name: _with_median(step) if name in MEDIAN else _adds_up(step) if name in ADDS_UP else step
    for name, step in _STEPS.items()
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


def _write(df: pl.DataFrame | dict[str, Any], out: Path, name: str) -> dict[str, str]:
    if isinstance(df, dict):
        file = f"{name}.geojson" if df.get("type") == "FeatureCollection" else f"{name}.json"
        text = json.dumps(df, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        (out / file).write_bytes(text.encode())
        return {file: _sha256(out / file)}
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
                rows = (
                    len(df["features"] if "features" in df else df["groups"])
                    if isinstance(df, dict)
                    else df.height
                )
                entry = {"inputs": inputs, "rows": rows, "sources": sources, "files": files}
                rebuilt.append(name)
                print(f"{name}: {rows} rows", flush=True)
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
