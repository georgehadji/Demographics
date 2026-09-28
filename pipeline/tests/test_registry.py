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
