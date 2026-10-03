"""Bibliography: DOI list -> verified CSL-JSON (PROPOSAL §8; IMPLEMENTATION-PLAN Δ5).

``data/bibliography/references.csv`` lists each work once: citation key, DOI, and the
title and author surnames the citing text expects. ``grpop-bib`` resolves every DOI
at doi.org by content negotiation (CSL-JSON from the registration agency, Crossref or
DataCite) and fails if a DOI does not resolve or its title or authors differ from the
expected ones. The output keeps the citation fields only: no abstract (the publisher's
text) and no counts that change daily, so two runs give the same bytes.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import httpx

from grpop.harmonize import REFERENCE
from grpop.sources.eurostat import fetch

REFERENCES = REFERENCE.parent / "bibliography" / "references.csv"
CSL = "application/vnd.citationstyles.csl+json"
FIELDS = (
    "type",
    "title",
    "author",
    "container-title",
    "issued",
    "volume",
    "issue",
    "page",
    "publisher",
    "DOI",
    "URL",
)


def normalise(text: str) -> str:
    """Case, accents, dashes and punctuation do not count: 'Lowest\u2010Low' == 'lowest-low'."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def read_references(path: Path = REFERENCES) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    keys = [r["key"] for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError(f"duplicate citation keys in {path.name}")
    return rows


def verified(expected: dict[str, str], csl: dict[str, Any]) -> dict[str, Any]:
    """The citation fields of ``csl`` with ``id`` = the key, if they match ``expected``."""
    errors = []
    if normalise(csl.get("title", "")) != normalise(expected["title"]):
        errors.append(f"title {csl.get('title')!r}")
    authors = [normalise(a.get("family", a.get("literal", ""))) for a in csl.get("author", [])]
    if authors != [normalise(a) for a in expected["authors"].split(";")]:
        errors.append(f"authors {authors}")
    if normalise(csl.get("DOI", "")) != normalise(expected["doi"]):
        errors.append(f"DOI {csl.get('DOI')!r}")
    if errors:
        raise ValueError(
            f"{expected['key']} ({expected['doi']}) does not match: {'; '.join(errors)}"
        )
    authors_out = [
        {k: a[k] for k in ("family", "given", "literal") if k in a} for a in csl.get("author", [])
    ]
    return {"id": expected["key"], **{k: csl[k] for k in FIELDS if k in csl}, "author": authors_out}


def resolve(client: httpx.Client, references: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        verified(r, json.loads(fetch(client, f"https://doi.org/{r['doi']}"))) for r in references
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve and check every DOI; write CSL-JSON.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    headers = {
        "Accept": CSL,
        "User-Agent": "kohortes-grpop (+https://github.com/georgehadji/Demographics)",
    }
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=60) as client:
            items = resolve(client, read_references())
    except (ValueError, httpx.HTTPError) as e:
        print(e, file=sys.stderr)
        return 1
    text = json.dumps(items, ensure_ascii=False, indent=1, sort_keys=True)
    args.out.write_bytes((text + "\n").encode())
    print(f"{len(items)} references verified", flush=True)
    return 0
