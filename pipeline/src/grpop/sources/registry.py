"""Typed access to the source registry (registry.yaml)."""

from __future__ import annotations

from datetime import date
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


class SourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    provider: str
    dataset_code: str
    title: str
    access: Literal["api", "bulk_file", "web_page", "pdf"]
    probe_kind: Literal["eurostat_jsonstat", "http"]
    probe_url: str = Field(pattern=r"^https://")
    licence: str
    used_for: list[str] = Field(min_length=1)
    phase: int = Field(ge=0, le=3)
    notes: str | None = None
    verification: Verification


def load_registry(text: str | None = None) -> list[SourceEntry]:
    """Load and validate the registry. Pass ``text`` to validate other YAML (tests)."""
    if text is None:
        text = resources.files("grpop.sources").joinpath("registry.yaml").read_text("utf-8")
    entries = [SourceEntry.model_validate(item) for item in yaml.safe_load(text)]
    ids = [e.id for e in entries]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate registry ids: {duplicates}")
    return entries
