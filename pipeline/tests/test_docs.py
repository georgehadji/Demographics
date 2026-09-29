"""Prose may name sources, but only the registry defines them (ADR 0006)."""

import re
from pathlib import Path
from urllib.parse import urlparse

from grpop.sources.registry import load_registry

ROOT = Path(__file__).resolve().parents[2]
# Living documents. ADRs, spikes and REVIEW.md are dated records and keep what was true then.
DOCS = [
    "README.md",
    "CLAUDE.md",
    "docs/PROPOSAL.md",
    "docs/IMPLEMENTATION-PLAN.md",
    "docs/landscape.md",
]


def test_readme_network_list_covers_every_probe_host():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    listed = set(re.search(r"Network access.*?```(.*?)```", readme, re.S).group(1).split())
    hosts = {urlparse(e.probe_url).hostname for e in load_registry()}
    assert hosts <= listed, sorted(hosts - listed)


# Eurostat theme prefixes. Project identifiers (e.g. `retrieved_at`) never start with these.
EUROSTAT_CODE = r"`((?:demo|proj|migr|hlth|cens|lfst|ilc|tps|tgs|sdg|nama|urb)_[a-z0-9_]*\*?)`"


def test_dataset_codes_named_in_docs_are_registered():
    codes = {e.dataset_code for e in load_registry()}
    named = {
        code
        for doc in DOCS
        for code in re.findall(EUROSTAT_CODE, (ROOT / doc).read_text(encoding="utf-8"))
    }
    # A trailing * names a family of datasets: at least one member must be registered.
    unknown = [
        n
        for n in named
        if not (any(c.startswith(n[:-1]) for c in codes) if n.endswith("*") else n in codes)
    ]
    assert not unknown, sorted(unknown)
