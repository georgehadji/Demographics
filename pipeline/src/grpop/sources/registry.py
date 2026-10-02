"""Typed access to the source registry (registry.yaml)."""

from __future__ import annotations

from datetime import date
from functools import cache
from importlib import resources
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Verification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["unverified", "verified", "failed"]
    checked_at: date | None = None
    evidence: str | None = None  # e.g. link to the probe report run

    @model_validator(mode="after")
    def evidence_required_once_checked(self) -> Verification:
        if self.status != "unverified" and (self.checked_at is None or not self.evidence):
            raise ValueError("verified/failed entries need checked_at and evidence")
        return self


class Licence(BaseModel):
    """Reuse terms of a source, as read from the provider's own terms page."""

    model_config = ConfigDict(extra="forbid")

    name: str
    terms_url: str = Field(pattern=r"^https://")
    attribution: str  # the credit line the provider asks for
    # False blocks publishing derived data under CC BY 4.0 (LICENSE-CONTENT.md).
    commercial_reuse: bool
    checked_at: date
    notes: str | None = None


class SourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    provider: str
    dataset_code: str
    title: str
    access: Literal["api", "bulk_file", "web_page", "pdf"]
    probe_kind: Literal["eurostat_jsonstat", "http"]
    probe_url: str = Field(pattern=r"^https://")
    # A file grpop-ingest stores as it is (the probe URL), checked as this format.
    # Eurostat datasets are ingested by their probe kind instead.
    ingest: Literal["geojson"] | None = None
    # A new entry may start as "to_verify"; the shipped registry may not (test_registry).
    licence: Licence | Literal["to_verify"]
    licence_key: str  # key into the registry's `licences` section, or "to_verify"
    used_for: list[str] = Field(min_length=1)
    phase: int = Field(ge=0, le=3)
    notes: str | None = None
    verification: Verification


@cache  # parsed once per process; callers must not mutate the result
def load_registry(text: str | None = None) -> list[SourceEntry]:
    """Load and validate the registry. Pass ``text`` to validate other YAML (tests).

    Each source names its licence by key; the key is resolved against the
    ``licences`` section, so every licence is written once (single source of truth).
    """
    if text is None:
        text = resources.files("grpop.sources").joinpath("registry.yaml").read_text("utf-8")
    doc = yaml.safe_load(text)
    if set(doc) != {"licences", "sources"}:
        raise ValueError("registry must have exactly 'licences' and 'sources'")
    licences = doc["licences"] or {}

    entries = []
    for item in doc["sources"]:
        key = item.get("licence")
        item = {**item, "licence_key": key}
        if key != "to_verify":
            if key not in licences:
                raise ValueError(f"{item.get('id')}: unknown licence key {key!r}")
            terms = dict(licences[key])
            terms["attribution"] = terms["attribution"].format(
                dataset_code=item.get("dataset_code")
            )
            item["licence"] = terms
        entries.append(SourceEntry.model_validate(item))

    ids = [e.id for e in entries]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate registry ids: {duplicates}")
    unused = sorted(set(licences) - {e.licence_key for e in entries})
    if unused:
        raise ValueError(f"licences not used by any source: {unused}")
    return entries


def get_source(source_id: str) -> SourceEntry:
    """The shipped registry entry with this id."""
    for entry in load_registry():
        if entry.id == source_id:
            return entry
    raise KeyError(f"no registry entry {source_id!r}")
