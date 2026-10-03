"""Bibliography: DOI resolution and checks, on a recorded CSL-JSON response."""

import json
from pathlib import Path

import httpx
import pytest
from test_eurostat import client

from grpop import bibliography

RECORDED = (Path(__file__).parent / "fixtures" / "csl_kohler2002.json").read_bytes()
REF = {
    "key": "kohler2002",
    "doi": "10.1111/j.1728-4457.2002.00641.x",
    "title": "The emergence of lowest-low fertility in Europe during the 1990s",
    "authors": "Kohler;Billari;Ortega",
}


def test_a_matching_doi_gives_citation_fields_only():
    c, seen = client([httpx.Response(200, content=RECORDED)])
    [item] = bibliography.resolve(c, [REF])
    assert str(seen[0].url) == f"https://doi.org/{REF['doi']}"
    assert item["id"] == "kohler2002"
    assert [a["family"] for a in item["author"]] == ["Kohler", "Billari", "Ortega"]
    assert not {"indexed", "is-referenced-by-count", "abstract", "_comment"} & set(item)
    assert item["container-title"] == "Population and Development Review"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("title", "The emergence of low fertility in Europe", "title"),
        ("authors", "Kohler;Ortega;Billari", "authors"),  # order counts
        ("authors", "Kohler;Billari", "authors"),
    ],
)
def test_a_doi_whose_title_or_authors_differ_is_refused(field, value, message):
    c, _ = client([httpx.Response(200, content=RECORDED)])
    with pytest.raises(ValueError, match=f"kohler2002 .* does not match: {message}"):
        bibliography.resolve(c, [{**REF, field: value}])


def test_a_doi_that_does_not_resolve_is_refused():
    c, _ = client([httpx.Response(404)])
    with pytest.raises(httpx.HTTPStatusError):
        bibliography.resolve(c, [REF])


def test_normalise_ignores_case_accents_and_dashes():
    assert bibliography.normalise("Lowest\u2010Low José") == bibliography.normalise(
        "lowest-low jose"
    )


def test_the_reference_list_has_unique_keys_and_the_expected_columns():
    rows = bibliography.read_references()
    assert rows and set(rows[0]) == {"key", "doi", "title", "authors"}
    assert json.loads(RECORDED)["DOI"] in {r["doi"] for r in rows}
