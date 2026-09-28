import pydantic
import pytest

from grpop.sources.registry import get_source, load_registry

ENTRY = """
- id: x
  provider: P
  dataset_code: c
  title: t
  access: api
  probe_kind: http
  probe_url: https://example.org
  licence: {licence}
  used_for: [a]
  phase: 1
  verification: {verification}
"""
LICENCE = """
  open:
    name: CC BY 4.0
    terms_url: https://example.org/terms
    attribution: 'Source: P, dataset {dataset_code}'
    commercial_reuse: true
    checked_at: 2026-10-01
"""


def registry(licence="to_verify", verification="{status: unverified}", licences=""):
    entry = ENTRY.replace("{licence}", licence).replace("{verification}", verification)
    return f"licences:{licences or ' {}'}\nsources:{entry}"


def test_shipped_registry_is_valid():
    entries = load_registry()
    assert len(entries) >= 10
    assert all(e.probe_url.startswith("https://") for e in entries)


def test_shipped_registry_has_no_unverified_licence():
    pending = [e.id for e in load_registry() if e.licence == "to_verify"]
    assert pending == []


def test_licence_is_resolved_by_key_with_dataset_code_filled_in():
    (entry,) = load_registry(registry(licence="open", licences=LICENCE))
    assert entry.licence_key == "open"
    assert entry.licence.attribution == "Source: P, dataset c"


def test_unknown_or_unused_licence_keys_are_errors():
    with pytest.raises(ValueError, match="unknown licence"):
        load_registry(registry(licence="missing", licences=LICENCE))
    with pytest.raises(ValueError, match="not used"):
        load_registry(registry(licences=LICENCE))


def test_licence_requires_https_terms_and_attribution():
    for bad in (
        LICENCE.replace("https://", "http://"),
        LICENCE.replace("    attribution: 'Source: P, dataset {dataset_code}'\n", ""),
        LICENCE + "    extra: 1\n",
    ):
        with pytest.raises((pydantic.ValidationError, KeyError)):
            load_registry(registry(licence="open", licences=bad))


def test_verified_entry_needs_evidence():
    with pytest.raises(pydantic.ValidationError):
        load_registry(registry(verification="{status: verified}"))
    load_registry(
        registry(verification="{status: verified, checked_at: 2026-10-01, evidence: probe run 1}")
    )


def test_duplicate_ids_rejected():
    text = registry()
    entry = text.split("sources:", 1)[1]
    with pytest.raises(ValueError, match="duplicate"):
        load_registry(text + entry)


def test_unknown_field_rejected():
    with pytest.raises(pydantic.ValidationError):
        load_registry(registry() + "  extra: 1\n")


def test_get_source_returns_shipped_entry():
    assert get_source("eurostat_demo_pjan").dataset_code == "demo_pjan"
    with pytest.raises(KeyError):
        get_source("no_such_source")
