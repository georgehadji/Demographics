"""Typed access to the metric definitions (definitions.yaml)."""

from __future__ import annotations

from importlib import resources

import yaml
from pydantic import BaseModel, ConfigDict, Field

from grpop.provenance import DEFINITION_ID_PATTERN


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=DEFINITION_ID_PATTERN)
    metric: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    title: str
    description: str


def load_definitions(text: str | None = None) -> dict[str, Definition]:
    """Load and validate the definitions. Pass ``text`` to validate other YAML (tests)."""
    if text is None:
        text = resources.files("grpop").joinpath("definitions.yaml").read_text("utf-8")
    definitions: dict[str, Definition] = {}
    for item in yaml.safe_load(text):
        definition = Definition.model_validate(item)
        if definition.id in definitions:
            raise ValueError(f"duplicate definition id: {definition.id}")
        definitions[definition.id] = definition
    return definitions


def get_definition(definition_id: str) -> Definition:
    """The shipped definition with this id."""
    try:
        return load_definitions()[definition_id]
    except KeyError:
        raise KeyError(f"no definition {definition_id!r} in definitions.yaml") from None
