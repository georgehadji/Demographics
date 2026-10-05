import pydantic
import pytest

from grpop.definitions import get_definition, load_definitions

ITEM = """
- id: {id}
  metric: m
  unit: persons
  title: t
  description: d
  el: {{title: τ, description: δ}}
"""


def test_shipped_definitions_are_valid():
    assert get_definition("population_1jan@v1").unit == "persons"


def test_duplicate_ids_rejected():
    text = ITEM.format(id="x@v1")
    with pytest.raises(ValueError, match="duplicate"):
        load_definitions(text + text)


def test_id_must_carry_a_version():
    with pytest.raises(pydantic.ValidationError):
        load_definitions(ITEM.format(id="population_1jan"))


def test_unknown_definition_is_an_error():
    with pytest.raises(KeyError):
        get_definition("no_such_metric@v1")
