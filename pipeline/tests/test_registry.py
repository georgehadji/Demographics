import pydantic
import pytest

from grpop.sources.registry import load_registry

ENTRY = """
- id: x
  provider: P
  dataset_code: c
  title: t
  access: api
  probe_kind: http
  probe_url: https://example.org
  licence: to_verify
  used_for: [a]
  phase: 1
  verification: {verification}
"""


def test_shipped_registry_is_valid():
    entries = load_registry()
    assert len(entries) >= 10
    assert all(e.probe_url.startswith("https://") for e in entries)


def test_shipped_registry_has_no_unverified_licence():
    pending = [e.id for e in load_registry() if e.licence == "to_verify"]
    assert pending == []


def test_licence_requires_https_terms_and_attribution():
    licence = (
        "{name: CC BY 4.0, terms_url: https://example.org/terms, attribution: 'Source: P',"
        " commercial_reuse: true, checked_at: 2026-10-01}"
    )
    base = ENTRY.format(verification="{status: unverified}")
    load_registry(base.replace("licence: to_verify", f"licence: {licence}"))

    for bad in (
        licence.replace("https://", "http://"),
        licence.replace(" attribution: 'Source: P',", ""),
        licence.replace("}", ", extra: 1}"),
    ):
        with pytest.raises(pydantic.ValidationError):
            load_registry(base.replace("licence: to_verify", f"licence: {bad}"))


def test_verified_entry_needs_evidence():
    with pytest.raises(pydantic.ValidationError):
        load_registry(ENTRY.format(verification="{status: verified}"))
    load_registry(
        ENTRY.format(
            verification="{status: verified, checked_at: 2026-10-01, evidence: probe run 1}"
        )
    )


def test_duplicate_ids_rejected():
    text = ENTRY.format(verification="{status: unverified}")
    with pytest.raises(ValueError, match="duplicate"):
        load_registry(text + text)


def test_unknown_field_rejected():
    text = ENTRY.format(verification="{status: unverified}") + "  extra: 1\n"
    with pytest.raises(pydantic.ValidationError):
        load_registry(text)
