"""Data release (IMPLEMENTATION-PLAN Δ6): ``grpop-publish``.

``package`` turns a data product (``grpop-build`` output) into one zip with the same
bytes for the same product: files in name order, fixed timestamps. It holds every
product file whose sources all allow commercial reuse (LICENSE-CONTENT.md: CC BY 4.0
cannot cover the others, e.g. the GISCO map geometry), ``manifest.json``,
``SOURCES.md`` (the terms and credit line of each source, from the registry),
``snapshots.txt`` (the sha256 of every snapshot read, for ``grpop-build --pin``) and
the release's ``CHANGELOG.md`` entry. ``deposit`` uploads it to Zenodo and publishes
it, as a new version of ``--concept`` when given; metadata come from CITATION.cff.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

import httpx
import yaml

from grpop.harmonize import REFERENCE
from grpop.sources.registry import get_source

ROOT = REFERENCE.parents[1]
CHANGELOG = ROOT / "publish" / "CHANGELOG.md"
CITATION = ROOT / "CITATION.cff"
_EPOCH = (1980, 1, 1, 0, 0, 0)


def changes(version: str) -> str:
    """The CHANGELOG entry of ``version``, which must be the newest one."""
    entries = re.split(r"^## ", CHANGELOG.read_text(encoding="utf-8"), flags=re.M)[1:]
    if not entries or not entries[0].startswith(f"{version} "):
        raise ValueError(f"the newest entry of {CHANGELOG.name} is not {version}")
    return "## " + entries[0].strip() + "\n"


def sources_text(manifest: dict[str, Any]) -> str:
    used = sorted({s["source_id"] for e in manifest.values() for s in e["sources"]})
    lines = ["# Sources and their terms", ""]
    for source_id in used:
        source = get_source(source_id)
        licence = source.licence
        assert licence != "to_verify"
        lines += [
            f"## {source.title}",
            f"- Provider: {source.provider}; dataset: {source.dataset_code}",
            f"- Licence: {licence.name} ({licence.terms_url})",
            f"- Credit: {licence.attribution}",
            "",
        ]
    return "\n".join(lines)


def _reusable(source_id: str) -> bool:
    licence = get_source(source_id).licence
    return licence != "to_verify" and licence.commercial_reuse


def _open(manifest: dict[str, Any]) -> list[str]:
    """Product files whose sources all allow commercial reuse."""
    return sorted(
        f
        for e in manifest.values()
        if all(_reusable(s["source_id"]) for s in e["sources"])
        for f in e["files"]
    )


def package(product: Path, version: str, out: Path) -> Path:
    manifest = json.loads((product / "manifest.json").read_bytes())
    snaps = sorted({s["sha256"] for e in manifest.values() for s in e["sources"]})
    extra = {
        "CHANGELOG.md": changes(version),
        "SOURCES.md": sources_text(manifest),
        "snapshots.txt": "\n".join(snaps) + "\n",
    }
    path = out / f"kohortes-data-{version}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted([*_open(manifest), "manifest.json", *extra]):
            info = zipfile.ZipInfo(name, _EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            data = extra[name].encode() if name in extra else (product / name).read_bytes()
            z.writestr(info, data)
    return path


def metadata(version: str) -> dict[str, Any]:
    cff = yaml.safe_load(CITATION.read_text(encoding="utf-8"))
    return {
        "upload_type": "dataset",
        "title": f"{cff['title']}: data release {version}",
        "creators": [{"name": f"{a['family-names']}, {a['given-names']}"} for a in cff["authors"]],
        "description": (
            "Data product of Kohortes: official series, derived indicators and projections "
            "for Greece and its peers, each value with its provenance. Third-party data "
            "stay under their terms (SOURCES.md).<br>" + changes(version).replace("\n", "<br>")
        ),
        "license": "cc-by-4.0",
        "keywords": cff["keywords"],
        "version": version,
        "related_identifiers": [
            {"relation": "isSupplementTo", "identifier": cff["repository-code"]}
        ],
    }


def deposit(client: httpx.Client, api: str, zipped: Path, version: str, concept: str | None) -> str:
    """Create (or version), upload, describe and publish; returns the DOI."""
    if concept:
        latest = client.get(f"{api}/records/{concept}").raise_for_status().json()
        draft = client.post(
            f"{api}/deposit/depositions/{latest['id']}/actions/newversion"
        ).raise_for_status()
        dep = client.get(draft.json()["links"]["latest_draft"]).raise_for_status().json()
        for f in dep.get("files", []):  # files carried over from the last version
            client.delete(f["links"]["self"]).raise_for_status()
    else:
        dep = client.post(f"{api}/deposit/depositions", json={}).raise_for_status().json()
    with zipped.open("rb") as f:
        client.put(f"{dep['links']['bucket']}/{zipped.name}", content=f.read()).raise_for_status()
    client.put(dep["links"]["self"], json={"metadata": metadata(version)}).raise_for_status()
    done = client.post(dep["links"]["publish"]).raise_for_status().json()
    return str(done["doi"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package the data product; deposit it on Zenodo.")
    parser.add_argument("--product", type=Path, required=True)
    parser.add_argument("--version", required=True, help="semver, e.g. 1.0.0")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--zenodo", help="API base, e.g. https://zenodo.org/api; needs ZENODO_TOKEN"
    )
    parser.add_argument("--concept", help="concept record id, to publish a new version")
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
            raise ValueError(f"version {args.version!r} is not semver")
        args.out.mkdir(parents=True, exist_ok=True)
        zipped = package(args.product, args.version, args.out)
        print(f"{zipped.name}: {zipped.stat().st_size} bytes", flush=True)
        if args.zenodo:
            headers = {"Authorization": f"Bearer {os.environ['ZENODO_TOKEN']}"}
            with httpx.Client(headers=headers, timeout=600, follow_redirects=True) as client:
                print(f"DOI: {deposit(client, args.zenodo, zipped, args.version, args.concept)}")
    except (ValueError, KeyError, httpx.HTTPError) as e:
        print(e, file=sys.stderr)
        return 1
    return 0
